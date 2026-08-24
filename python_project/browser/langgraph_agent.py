
"""LangGraph Autonomous Browser Agent, powered by Stagehand's `act`/`observe`/
`extract`/navigate AI-native primitives instead of hand-rolled selector/element
tooling. Same StateGraph shape (deterministic loop, `finish_task` terminal
tool, iteration guardrail) as the Sandbox Agent, so both specialists behave
consistently and support the same on-demand cross-agent handoff.
"""
import os
import time
import operator
from typing import Annotated, Any, Dict, List, Optional, Sequence, Tuple, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph

from agent.async_manager import AgentRunState, async_agent_manager
from agent.handoff import bind_handoff_tools
from agent.prompts import CONCISE_FINAL_ANSWER_DIRECTIVE
from browser.context import get_current_thread_id, get_current_user_id
from browser.schema import BrowserMode, PolicyStrategy
from browser.security_manager import security_manager
from browser.service import browser_service
from models import LLMCancelledError, LLMTimeoutError, get_chat_model, invoke_llm_with_diagnostics

MAX_ITERATIONS = 10


# ============================================================================
# Stagehand-backed browser tools
# ============================================================================

@tool
def browser_navigate(url: str) -> str:
    """
    Navigate the browser to a specific web URL. Use for going to a known site
    directly (e.g. 'https://github.com', 'naukri.com').
    Args:
        url: Destination web address.
    """
    res = browser_service.navigate(user_id=get_current_user_id(), url=url, thread_id=get_current_thread_id())
    return res.message


@tool
def browser_act(instruction: str) -> str:
    """
    Perform an action on the current webpage described in plain natural language
    (Stagehand resolves the target element itself — no selectors needed).
    Examples: "click the Sign In button", "type 'python developer' into the search box",
    "scroll down to the pricing section", "check the 'remember me' checkbox".
    Args:
        instruction: A precise, single natural-language action to perform.
    """
    res = browser_service.act(user_id=get_current_user_id(), instruction=instruction, thread_id=get_current_thread_id())
    if res.status == "confirmation_required":
        return (
            f"⚠️ This action requires human confirmation before it can proceed: {res.message}\n"
            f"Confirmation ID: {res.data.get('confirmation_id') if res.data else 'unknown'}. "
            "Ask the user to approve or reject it — do not attempt it again until approved."
        )
    return res.message


@tool
def browser_observe(instruction: Optional[str] = None) -> str:
    """
    Discover what actionable elements (buttons, links, inputs) exist on the current
    page, optionally focused by an instruction (e.g. 'find the submit buttons').
    Use this before `browser_act` when you are unsure what's clickable.
    Args:
        instruction: Optional focus hint for what kind of elements to look for.
    """
    res = browser_service.observe(user_id=get_current_user_id(), instruction=instruction, thread_id=get_current_thread_id())
    return res.message


@tool
def browser_extract(instruction: str) -> str:
    """
    Extract structured or free-text data from the current webpage described in
    plain natural language. Use this to read/scrape the page's real content
    (e.g. 'extract all job titles and companies listed', 'get the price shown').
    Args:
        instruction: What information to extract from the page.
    """
    res = browser_service.extract(user_id=get_current_user_id(), instruction=instruction, thread_id=get_current_thread_id())
    return res.message


@tool
def finish_task(result: str) -> str:
    """
    Call this exactly once, as the LAST step, when the browser task is fully
    complete. `result` must be the complete, final, user-facing Markdown answer —
    it is the ONLY thing shown to the user; all earlier tool chatter is discarded.
    Args:
        result: The final concrete answer/summary for the user.
    """
    return result


BROWSER_AGENT_TOOLS = [browser_navigate, browser_act, browser_observe, browser_extract, finish_task]

TOOL_DISPLAY_MAP: Dict[str, Tuple[str, str]] = {
    "browser_navigate": ("browser-agent", "Browser Navigation"),
    "browser_act": ("browser-agent", "Browser Action"),
    "browser_observe": ("browser-agent", "Browser Observation"),
    "browser_extract": ("browser-agent", "Browser Data Extraction"),
    "finish_task": ("browser-agent", "Task Completion"),
    "delegate_to_sandbox_agent": ("sandbox-agent", "Handoff -> Sandbox Agent"),
    "delegate_to_research_agent": ("web-search", "Handoff -> Research Agent"),
}

SYSTEM_INSTRUCTION_GRAPH = (
    "You are Clever AI's Browser Agent, powered by Stagehand — an AI-native browser "
    "automation engine. You do NOT need CSS selectors or element IDs: describe what you "
    "want in plain language and Stagehand resolves it.\n\n"
    "=== OPERATIONAL INSTRUCTIONS ===\n"
    "1. Start with 'browser_navigate' to reach the target site if you are not already there.\n"
    "2. Use 'browser_act' for interactions (click, type, scroll, select) — one clear "
    "instruction per call. Use 'browser_observe' first only if you are unsure what's on the page.\n"
    "3. Use 'browser_extract' to read/scrape real page content — never fabricate data you "
    "have not actually extracted.\n"
    "4. If a 'browser_act' call reports it needs human confirmation, STOP and surface that "
    "clearly in your final answer instead of retrying — do not attempt to bypass it.\n"
    "5. If the task needs local code execution or fresh general web research beyond this "
    "page, call 'delegate_to_sandbox_agent' / 'delegate_to_research_agent' instead of guessing.\n"
    "6. TERMINATION DISCIPLINE: once the task is verified complete, call "
    "'finish_task(result=...)' with the full Markdown summary — including the exact data "
    "you extracted or the exact outcome observed. Only this output is shown to the user.\n"
    f"{CONCISE_FINAL_ANSWER_DIRECTIVE}"
)


class BrowserState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task_complete: bool
    final_result: Optional[str]
    step_count: int
    user_id: int
    run_id: str
    tool_results: List[Dict[str, Any]]
    thread_id: str


def _build_tools_for_run(run_id: str, user_id: int, thread_id: str) -> List[Any]:
    return BROWSER_AGENT_TOOLS + bind_handoff_tools(run_id=run_id, user_id=user_id, thread_id=thread_id)


def agent_node(state: BrowserState) -> Dict[str, Any]:
    run_id = state["run_id"]
    if async_agent_manager.is_cancelled(run_id):
        raise LLMCancelledError("Run was cancelled before agent step.")

    tools = _build_tools_for_run(run_id, state["user_id"], state["thread_id"])
    llm = get_chat_model().bind_tools(tools)

    response = invoke_llm_with_diagnostics(llm, list(state["messages"]), run_id=run_id, iteration=state["step_count"] + 1)
    return {"messages": [response], "step_count": state["step_count"] + 1}


def tool_node(state: BrowserState) -> Dict[str, Any]:
    run_id = state["run_id"]
    tools = _build_tools_for_run(run_id, state["user_id"], state["thread_id"])
    tool_map = {t.name: t for t in tools}

    last_message = state["messages"][-1]
    tool_messages: List[BaseMessage] = []
    tool_results = list(state.get("tool_results", []))
    final_result = None
    task_complete = False

    for call in getattr(last_message, "tool_calls", []) or []:
        name = call["name"]
        args = call.get("args", {})
        start = time.time()
        try:
            output = tool_map[name].invoke(args) if name in tool_map else f"Unknown tool '{name}'."
        except Exception as exc:
            output = f"Tool '{name}' error: {exc}"

        duration_ms = int((time.time() - start) * 1000)
        label = TOOL_DISPLAY_MAP.get(name, ("browser-agent", name))
        tool_results.append({"tool": label[1], "plugin": label[0], "duration_ms": duration_ms, "output": str(output)[:2000]})
        async_agent_manager.log_timing(run_id, f"tool_{name}", duration_ms, iteration=state["step_count"])

        if name == "finish_task":
            final_result = str(output)
            task_complete = True

        tool_messages.append(ToolMessage(content=str(output), tool_call_id=call["id"]))

    return {"messages": tool_messages, "tool_results": tool_results, "final_result": final_result, "task_complete": task_complete}


def should_continue(state: BrowserState) -> str:
    if state.get("task_complete"):
        return "end"
    if state["step_count"] >= MAX_ITERATIONS:
        return "end"
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "end"


browser_agent_graph_builder = StateGraph(BrowserState)
browser_agent_graph_builder.add_node("agent", agent_node)
browser_agent_graph_builder.add_node("tools", tool_node)
browser_agent_graph_builder.set_entry_point("agent")
browser_agent_graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
browser_agent_graph_builder.add_edge("tools", "agent")
browser_agent_graph = browser_agent_graph_builder.compile()


def run_langgraph_browser_agent(
    user_prompt: str,
    active_plugin_ids: Optional[List[str]] = None,
    document_context: Optional[List[Dict[str, Any]]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: int = 1,
    run_id: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]], str]:
    """Executes the LangGraph StateGraph Browser Agent (Stagehand-backed)."""
    policy = browser_service.evaluate_intent(user_prompt, user_id=user_id)
    if policy.strategy == PolicyStrategy.PROMPT_USER_TO_CONNECT:
        return (
            "### ⚠️ Existing Browser Connection Required\n\n"
            "I detected that this task involves your private authenticated account (such as Gmail, GitHub notifications, or private dashboards). "
            "To access your account securely without entering passwords:\n\n"
            "1. Start your browser with remote debugging:\n"
            "   `google-chrome --remote-debugging-port=9222 --user-data-dir=\"/tmp/chrome_dev_agent\"`\n"
            "2. Click the **Compass (`🧭`)** icon in the header and click **Connect**.\n\n"
            "Once connected, I will interact with your existing logged-in browser session!",
            [],
            "LangGraph Autonomous Browser Agent (Stagehand)",
        )

    if policy.strategy == PolicyStrategy.LAUNCH_MANAGED:
        status = browser_service.get_status(user_id=user_id)
        if not status.connected:
            browser_service.connect(user_id=user_id, mode=BrowserMode.MANAGED_BROWSER)

    actual_run_id = run_id
    if not actual_run_id or not async_agent_manager.get_run(actual_run_id):
        r_rec = async_agent_manager.create_run(
            user_id=user_id, thread_id=thread_id or "default-thread", prompt=user_prompt,
            model=os.getenv("DEFAULT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"), run_id=actual_run_id,
        )
        actual_run_id = r_rec.run_id

    async_agent_manager.set_state(actual_run_id, AgentRunState.RUNNING)

    initial_messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_INSTRUCTION_GRAPH)]
    if history:
        for msg in history[-10:]:
            if msg.get("role") == "user":
                initial_messages.append(HumanMessage(content=msg.get("content", "")))
            else:
                initial_messages.append(AIMessage(content=msg.get("content", "")))

    doc_note = ""
    if document_context:
        doc_note = "\n\nAttached Documents:\n" + "\n".join(f"- {c.get('filename')}: {c.get('content')[:300]}" for c in document_context)

    initial_messages.append(HumanMessage(content=f"{user_prompt}{doc_note}"))

    initial_state: BrowserState = {
        "messages": initial_messages,
        "task_complete": False,
        "final_result": None,
        "step_count": 0,
        "user_id": user_id,
        "run_id": actual_run_id,
        "tool_results": [],
        "thread_id": thread_id or "default-thread",
    }

    try:
        final_state = browser_agent_graph.invoke(initial_state)
        final_output = final_state.get("final_result")

        if not final_output or len(final_output.strip()) < 15:
            last_msg = final_state["messages"][-1] if final_state["messages"] else None
            if last_msg and isinstance(last_msg.content, str) and len(last_msg.content.strip()) > 30:
                final_output = last_msg.content.strip()
            else:
                # Local imports avoid a circular import at module load time
                # (tools/__init__.py imports tools.executor, which imports this module).
                from tools.job_intelligence import fetch_and_rank_jobs
                from tools.web_search import perform_web_search
                lower = user_prompt.lower()
                if any(w in lower for w in ["job", "naukri", "career", "hiring", "opening"]):
                    job_res = fetch_and_rank_jobs(user_prompt)
                    final_output = job_res["formatted"]
                else:
                    search_res = perform_web_search(user_prompt, max_results=5)
                    final_output = search_res["formatted"]

        tool_results_list = final_state.get("tool_results", [])
        async_agent_manager.complete_run(actual_run_id, final_output, tool_results_list)
        return final_output, tool_results_list, "LangGraph Autonomous Browser Agent (Stagehand)"

    except LLMTimeoutError as te:
        async_agent_manager.complete_run(actual_run_id, "The agent timed out waiting for the LLM response.", [], error="LLM_TIMEOUT", is_timeout=True)
        raise te
    except LLMCancelledError as ce:
        async_agent_manager.complete_run(actual_run_id, "Execution was cancelled.", [], error="CANCELLED")
        raise ce
    except Exception as e:
        async_agent_manager.complete_run(actual_run_id, str(e), [], error=str(e))
        raise e

