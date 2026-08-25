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
from agent.verification import verify_completion_claim
from memory.persistent_store import get_facts_as_context
from browser.context import get_current_thread_id, get_current_user_id, get_current_run_id
from browser.schema import BrowserMode, PolicyStrategy
from browser.security_manager import security_manager
from browser.service import browser_service
from models import LLMCancelledError, LLMTimeoutError, get_chat_model, invoke_llm_with_diagnostics

MAX_ITERATIONS = 10


# ============================================================================
# Stagehand-backed browser tools
# ============================================================================

# Status tag prefixes so the LLM (and the no-progress heuristic in tool_node)
# can reliably tell these outcomes apart from a plain successful message,
# instead of the agent guessing from prose alone.
_STATUS_TAGS = {
    "unavailable": "[BROWSER_UNAVAILABLE] ",
    "timeout": "[EXECUTION_TIMEOUT] ",
    "auth_required": "[AUTH_REQUIRED] ",
    "no_results": "[NO_RESULTS] ",
}


def _tag_message(res) -> str:
    prefix = _STATUS_TAGS.get(res.status, "")
    return f"{prefix}{res.message}" if prefix else res.message


def _log_timing_breakdown(action: str, res) -> None:
    """
    Surfaces real sub-span latency (item 3) instead of hiding the whole
    browser operation behind one opaque duration — logged as a distinct
    telemetry event so the frontend's ActivityTimeline can show, e.g.,
    "stagehand_reasoning_ms: 4200" as its own step rather than one generic
    216351ms "browser-agent" blob.
    """
    breakdown = getattr(res, "timing_breakdown", None)
    if not breakdown:
        return
    run_id = get_current_run_id()
    if not run_id:
        return
    for stage, ms in breakdown.items():
        if ms:
            async_agent_manager.log_timing(run_id, f"browser_{action}_{stage}", ms, tool=f"browser_{action}")


@tool
def browser_navigate(url: str) -> str:
    """
    Navigate the browser to a specific web URL. Use for going to a known site
    directly (e.g. 'https://github.com', 'naukri.com').
    Args:
        url: Destination web address.
    """
    res = browser_service.navigate(user_id=get_current_user_id(), url=url, thread_id=get_current_thread_id())
    _log_timing_breakdown("navigate", res)
    return _tag_message(res)


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
    _log_timing_breakdown("act", res)
    return _tag_message(res)


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
    _log_timing_breakdown("observe", res)
    return _tag_message(res)


@tool
def browser_extract(instruction: str) -> str:
    """
    Extract structured or free-text data from the current webpage described in
    plain natural language. Use this to read/scrape the page's real content
    (e.g. 'extract all job titles and companies listed', 'get the price shown').
    Args:
        instruction: What information to extract from the page.
    """
    # Local import to avoid a circular import: tools/__init__.py eagerly imports
    # tools.executor, which imports this module — importing tools.tool_cache at
    # module load time here would trigger that cycle.
    from tools.tool_cache import cached_call

    user_id = get_current_user_id()
    thread_id = get_current_thread_id()
    # Short-TTL cache: avoids re-running an identical, expensive Stagehand
    # extraction if the agent (or a self-verification pass) repeats the same
    # instruction on the same page within a few seconds.
    cache_args = {"user_id": user_id, "thread_id": thread_id, "instruction": instruction}
    result, _ = cached_call(
        "browser_extract", cache_args,
        lambda: browser_service.extract(user_id=user_id, instruction=instruction, thread_id=thread_id),
        ttl_seconds=20,
    )
    _log_timing_breakdown("extract", result)
    return _tag_message(result)


@tool
def finish_task(
    result: str,
    status: str = "completed",
    verified_count: Optional[int] = None,
    requested_count: Optional[int] = None,
) -> str:
    """
    Call this exactly once, as the LAST step, whenever you stop acting on the
    browser task — whether you fully succeeded, partially succeeded, or could
    not proceed. `result` must be the complete, final, user-facing Markdown
    answer — it is the ONLY thing shown to the user; all earlier tool chatter
    is discarded.

    You MUST set `status` honestly based on what you actually verified on the
    page via browser_observe/browser_extract — NOT based on whether a tool
    call merely executed without raising an exception:
      - "completed": you verified every part of the user's request (e.g. all
        N requested items were found and confirmed on the page).
      - "partial": you verified some but not all requested items/criteria.
        Always set verified_count and requested_count in this case.
      - "no_results": navigation/search executed successfully but the page
        genuinely has no data matching the request. This is NOT a failure —
        do not describe the tool as "unavailable" in this case.
      - "waiting_for_user": you cannot proceed further without the user doing
        something themselves (e.g. logging in, solving a CAPTCHA, 2FA).
      - "failed": the browser task could not be completed due to a real
        execution problem (timeout, navigation failure, blocked action) that
        is unrelated to data availability.
    Args:
        result: The final concrete Markdown answer for the user.
        status: One of "completed", "partial", "no_results", "waiting_for_user", "failed".
        verified_count: How many requested items you actually verified (omit if not applicable).
        requested_count: How many items/criteria the user actually asked for (omit if not applicable).
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

# Consecutive "no progress" tool outputs (empty / no-results / not-found) before
# the agent is forced to stop and honestly report NO_RESULTS instead of
# looping through the same ineffective strategy over and over.
MAX_CONSECUTIVE_NO_PROGRESS = 3
_NO_PROGRESS_MARKERS = (
    "no actionable elements found", "no live search results", "no results",
    "not found", "no matching", "nothing found", "could not find",
)


def _looks_like_no_progress(output: str) -> bool:
    text = (output or "").strip().lower()
    if not text:
        return True
    return any(marker in text for marker in _NO_PROGRESS_MARKERS)


STATUS_TO_RUN_STATE: Dict[str, AgentRunState] = {
    "completed": AgentRunState.COMPLETED,
    "partial": AgentRunState.PARTIAL,
    "no_results": AgentRunState.NO_RESULTS,
    "waiting_for_user": AgentRunState.WAITING_FOR_USER,
    "failed": AgentRunState.FAILED,
    "tool_unavailable": AgentRunState.TOOL_UNAVAILABLE,
}

SYSTEM_INSTRUCTION_GRAPH = (
    "You are Clever AI's Browser Agent, powered by Stagehand — an AI-native browser "
    "automation engine. You do NOT need CSS selectors or element IDs: describe what you "
    "want in plain language and Stagehand resolves it.\n\n"
    "=== OPERATIONAL INSTRUCTIONS ===\n"
    "1. Start with 'browser_navigate' to reach the target site if you are not already there.\n"
    "2. Use 'browser_act' for interactions (click, type, scroll, select) — one clear "
    "instruction per call. Use 'browser_observe' first only if you are unsure what's on the page. "
    "If 'browser_act' fails, it automatically re-scans the page and includes fresh candidate elements "
    "in its error message — use those to retry with a more precise instruction instead of repeating the same one.\n"
    "3. Use 'browser_extract' to read/scrape real page content — never fabricate data you "
    "have not actually extracted.\n"
    "4. If a 'browser_act' call reports it needs human confirmation, STOP and surface that "
    "clearly in your final answer instead of retrying — do not attempt to bypass it.\n"
    "5. If the task needs local code execution or fresh general web research beyond this "
    "page, call 'delegate_to_sandbox_agent' / 'delegate_to_research_agent' instead of guessing.\n"
    "6. TERMINATION DISCIPLINE — CRITICAL: a tool call succeeding (no exception) does NOT mean "
    "the user's goal is complete. Before calling 'finish_task', check whether you have actually "
    "VERIFIED the specific data/outcome the user asked for via browser_extract/browser_observe. "
    "Always call 'finish_task(result=..., status=...)' with an honest status:\n"
    "   - 'completed' only if you verified every requested item/criterion.\n"
    "   - 'partial' if you verified some but not all — set verified_count/requested_count.\n"
    "   - 'no_results' if the page genuinely has no matching data (this is NOT a tool failure "
    "and must never be described as 'unavailable').\n"
    "   - 'waiting_for_user' if the user must act themselves (login, CAPTCHA, 2FA).\n"
    "   - 'failed' only for a real execution problem (timeout/navigation/blocked action).\n"
    "7. Never claim a browser tool is 'unavailable' just because a search or extraction "
    "returned nothing — that is 'no_results', a normal outcome, not unavailability.\n"
    "8. Do not repeat the exact same ineffective action/search more than twice in a row — if a "
    "strategy isn't producing new information, try a different approach or call 'finish_task' "
    "honestly reporting what you found (or didn't).\n"
    f"{CONCISE_FINAL_ANSWER_DIRECTIVE}"
)


class BrowserState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task_complete: bool
    final_result: Optional[str]
    completion_status: str
    verified_count: Optional[int]
    requested_count: Optional[int]
    consecutive_no_progress: int
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
    completion_status = state.get("completion_status", "partial")
    verified_count = state.get("verified_count")
    requested_count = state.get("requested_count")
    consecutive_no_progress = state.get("consecutive_no_progress", 0)

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
            completion_status = str(args.get("status") or "completed")
            verified_count = args.get("verified_count")
            requested_count = args.get("requested_count")
        elif "[BROWSER_UNAVAILABLE]" in str(output):
            # Genuine capability unavailability is terminal immediately — don't
            # wait for the no-progress streak or keep retrying a tool that
            # cannot currently be used at all.
            task_complete = True
            completion_status = "tool_unavailable"
            final_result = str(output).replace("[BROWSER_UNAVAILABLE] ", "")
        elif "[AUTH_REQUIRED]" in str(output):
            task_complete = True
            completion_status = "waiting_for_user"
            final_result = str(output).replace("[AUTH_REQUIRED] ", "")
        elif name in ("browser_observe", "browser_extract", "delegate_to_research_agent"):
            if _looks_like_no_progress(str(output)):
                consecutive_no_progress += 1
            else:
                consecutive_no_progress = 0
        else:
            # Navigation/act/other tools genuinely changed state — don't count
            # them toward the no-progress streak either way.
            pass

        tool_messages.append(ToolMessage(content=str(output), tool_call_id=call["id"]))

    # Repeated-failed-strategy guard: if the agent keeps getting no-results from
    # its data-gathering tools without ever calling finish_task, stop looping
    # and honestly report NO_RESULTS instead of burning the full iteration budget.
    if not task_complete and consecutive_no_progress >= MAX_CONSECUTIVE_NO_PROGRESS:
        task_complete = True
        completion_status = "no_results"
        final_result = (
            "I searched/observed the page multiple times but consistently found no "
            "matching results, so I'm stopping here rather than repeating the same "
            "ineffective approach. No data could be verified for this request."
        )

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "final_result": final_result,
        "task_complete": task_complete,
        "completion_status": completion_status,
        "verified_count": verified_count,
        "requested_count": requested_count,
        "consecutive_no_progress": consecutive_no_progress,
    }


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
    user_facts_context = get_facts_as_context(user_id)
    if user_facts_context:
        initial_messages.append(SystemMessage(
            content=f"=== LONG-TERM USER MEMORY ===\n{user_facts_context}\n=== END LONG-TERM USER MEMORY ==="
        ))
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
        "completion_status": "partial",
        "verified_count": None,
        "requested_count": None,
        "consecutive_no_progress": 0,
        "step_count": 0,
        "user_id": user_id,
        "run_id": actual_run_id,
        "tool_results": [],
        "thread_id": thread_id or "default-thread",
    }

    try:
        final_state = browser_agent_graph.invoke(initial_state)
        final_output = final_state.get("final_result")
        completion_status_str = final_state.get("completion_status") or "partial"
        verified_count = final_state.get("verified_count")
        requested_count = final_state.get("requested_count")
        tool_results_list = final_state.get("tool_results", [])

        if not final_state.get("task_complete") or not final_output or len(final_output.strip()) < 15:
            # `finish_task` was NEVER called (e.g. the loop hit MAX_ITERATIONS
            # without the LLM explicitly declaring a verdict). Previously this
            # silently substituted a fresh, UNRELATED web_search/job-search call
            # and returned it as if it were the browser agent's verified result —
            # which is exactly the false-completion bug this fix removes. Instead,
            # report honestly based on what the browser agent actually did.
            last_msg = final_state["messages"][-1] if final_state["messages"] else None
            observed_text = (
                last_msg.content.strip()
                if last_msg and isinstance(last_msg.content, str) and len(last_msg.content.strip()) > 30
                else None
            )
            completion_status_str = "partial" if tool_results_list else "failed"
            if observed_text:
                final_output = (
                    f"{observed_text}\n\n"
                    "_Note: I was unable to fully verify completion of this task within the "
                    "allotted steps — treat the above as partial, unverified progress rather "
                    "than a confirmed final result._"
                )
            else:
                final_output = (
                    "I was unable to complete or verify this browser task within the allotted "
                    "steps. No verified result is available yet — this is not a tool "
                    "availability issue, the task simply did not finish in time."
                )

        # TASK VERIFICATION: cross-check the self-reported verdict against what
        # was ACTUALLY extracted from the page instead of trusting the LLM's
        # claim unconditionally. If the user asked for e.g. "5 latest jobs" but
        # the extracted content only contains 2 list items, downgrade the
        # claimed "completed" to an honest "partial" before this ever reaches
        # the user or the run record.
        adj_status, adj_verified, adj_requested, verify_note = verify_completion_claim(
            user_prompt=user_prompt,
            tool_results=tool_results_list,
            claimed_status=completion_status_str,
            claimed_verified_count=verified_count,
            claimed_requested_count=requested_count,
        )
        if verify_note:
            final_output = f"{final_output}\n\n_Verification note: {verify_note}_"
        completion_status_str, verified_count, requested_count = adj_status, adj_verified, adj_requested

        run_state = STATUS_TO_RUN_STATE.get(completion_status_str, AgentRunState.COMPLETED)
        async_agent_manager.complete_run(
            actual_run_id, final_output, tool_results_list,
            completion_status=run_state, verified_count=verified_count, requested_count=requested_count,
        )
        return final_output, tool_results_list, "LangGraph Autonomous Browser Agent (Stagehand)"

    except LLMTimeoutError as te:
        async_agent_manager.complete_run(
            actual_run_id, "The agent timed out waiting for the LLM response.", [],
            error="LLM_TIMEOUT", is_timeout=True, completion_status=AgentRunState.TIMEOUT,
        )
        raise te
    except LLMCancelledError as ce:
        async_agent_manager.complete_run(
            actual_run_id, "Execution was cancelled.", [],
            error="CANCELLED", completion_status=AgentRunState.CANCELLED,
        )
        raise ce
    except Exception as e:
        async_agent_manager.complete_run(actual_run_id, str(e), [], error=str(e), completion_status=AgentRunState.FAILED)
        raise e
