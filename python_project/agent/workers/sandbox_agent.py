"""LangGraph Autonomous Sandbox Agent: an iterative execute -> observe -> decide loop
for local code/shell execution, file I/O, and script iteration.

Mirrors the architecture of `browser/langgraph_agent.py` (same StateGraph shape,
terminal `finish_sandbox_task` tool, iteration guardrail) so both specialist agents
behave consistently and can be extended the same way. It also binds the on-demand
handoff tools (`agent.handoff`) so it can delegate to the Browser or Research agent
mid-task without being statically wired to only one capability.
"""
import operator
import os
import time
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from agent.async_manager import AgentRunState, async_agent_manager
from agent.handoff import bind_handoff_tools
from agent.prompts import CONCISE_FINAL_ANSWER_DIRECTIVE
from agent.verification import verify_completion_claim
from memory.persistent_store import get_facts_as_context
from config import settings
from models import LLMCancelledError, LLMTimeoutError, get_chat_model, invoke_llm_with_diagnostics
from tools.sandbox_tools import ALL_SANDBOX_TOOLS

MAX_ITERATIONS = settings.sandbox_max_iterations

SANDBOX_TOOL_MAP = {t.name: t for t in ALL_SANDBOX_TOOLS}

# Maps the honest `status` argument the LLM passes to `finish_sandbox_task`
# onto the run's true terminal state — never collapse every non-error outcome
# into a blanket COMPLETED.
STATUS_TO_RUN_STATE: Dict[str, AgentRunState] = {
    "completed": AgentRunState.COMPLETED,
    "partial": AgentRunState.PARTIAL,
    "no_results": AgentRunState.NO_RESULTS,
    "failed": AgentRunState.FAILED,
}

TOOL_DISPLAY_MAP: Dict[str, Tuple[str, str]] = {
    "execute_shell_command": ("sandbox-agent", "Sandbox Shell Execution"),
    "execute_python_code": ("sandbox-agent", "Sandbox Python Execution"),
    "read_file": ("sandbox-agent", "Sandbox File Read"),
    "write_file": ("sandbox-agent", "Sandbox File Write"),
    "list_directory": ("sandbox-agent", "Sandbox Directory Listing"),
    "finish_sandbox_task": ("sandbox-agent", "Sandbox Task Completion"),
    "delegate_to_browser_agent": ("browser-agent", "Handoff -> Browser Agent"),
    "delegate_to_sandbox_agent": ("sandbox-agent", "Handoff -> Sandbox Agent"),
    "delegate_to_research_agent": ("web-search", "Handoff -> Research Agent"),
}

SYSTEM_INSTRUCTION_SANDBOX = (
    "You are Clever AI's Sandbox Agent — an autonomous code/command execution specialist. "
    "You run in an unsandboxed **local development** environment (no container isolation yet); "
    "act carefully and never run destructive commands (mass deletion, formatting drives, "
    "modifying system files) unless the user explicitly and unambiguously asked for exactly that.\n\n"
    "=== OPERATIONAL INSTRUCTIONS ===\n"
    "1. Operate in a Perceive -> Decide -> Act loop: execute a command/script, read its real "
    "output, then decide the next step.\n"
    "2. Prefer 'execute_python_code' for computation/data-processing; use 'execute_shell_command' "
    "for installs, filesystem operations, or running external programs.\n"
    "3. If a task needs live browser interaction or fresh web research, call "
    "'delegate_to_browser_agent' / 'delegate_to_research_agent' instead of guessing.\n"
    "4. TERMINATION DISCIPLINE — CRITICAL: a command succeeding (exit code 0 / no exception) does "
    "NOT mean the user's goal is complete. Verify the actual output before finishing. Call "
    "'finish_sandbox_task(result=..., status=...)' with an honest status: 'completed' only if you "
    "verified the requested outcome, 'partial' if only some of it was accomplished, 'no_results' if "
    "commands ran fine but produced no matching data, 'failed' only for a real unrecoverable error.\n"
    "5. If a command fails, inspect stderr, adapt (fix code / install missing dependency / "
    "adjust command) and retry — do not give up after a single failure unless clearly unrecoverable. "
    "But do not repeat the exact same failing command more than twice without changing approach.\n"
    f"{CONCISE_FINAL_ANSWER_DIRECTIVE}"
)


class SandboxState(TypedDict):
    """LangGraph State Schema for the Sandbox Agent."""
    messages: Annotated[List[BaseMessage], operator.add]
    task_complete: bool
    final_result: Optional[str]
    completion_status: str
    step_count: int
    user_id: int
    run_id: str
    thread_id: str
    tool_results: List[Dict[str, Any]]


def _tools_for(state: SandboxState) -> List[Any]:
    handoff_tools = bind_handoff_tools(
        run_id=state.get("run_id", "default_run"),
        user_id=state.get("user_id", 1),
        thread_id=state.get("thread_id", "default-thread"),
    )
    return ALL_SANDBOX_TOOLS + handoff_tools


def agent_node(state: SandboxState) -> Dict[str, Any]:
    """Reasoning node: LLM inspects messages and decides next tool call or finish_sandbox_task."""
    run_id = state.get("run_id", "default_run")
    step = state.get("step_count", 0)

    if async_agent_manager.is_cancelled(run_id):
        return {"task_complete": True, "final_result": "Execution was cancelled by user."}

    async_agent_manager.set_state(run_id, AgentRunState.WAITING_FOR_LLM, f"Sandbox planning step {step + 1}")
    llm = get_chat_model()
    tools = _tools_for(state)
    llm_with_tools = llm.bind_tools(tools)

    messages = list(state["messages"])
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_INSTRUCTION_SANDBOX)] + messages

    response = invoke_llm_with_diagnostics(llm_with_tools, messages, run_id=run_id, iteration=step + 1)

    task_complete = False
    final_result = None
    completion_status = state.get("completion_status", "partial")
    if getattr(response, "tool_calls", None):
        for tc in response.tool_calls:
            if tc.get("name") == "finish_sandbox_task":
                task_complete = True
                final_result = tc.get("args", {}).get("result", "")
                completion_status = str(tc.get("args", {}).get("status") or "completed")
                break

    if not task_complete and not getattr(response, "tool_calls", None):
        text_content = response.content if isinstance(response.content, str) else ""
        if text_content and len(text_content.strip()) > 30:
            task_complete = True
            final_result = text_content.strip()
            # The LLM stopped calling tools without an explicit finish_sandbox_task
            # verdict — treat this as PARTIAL rather than assuming full success.
            completion_status = "partial"

    return {
        "messages": [response],
        "task_complete": task_complete,
        "final_result": final_result,
        "completion_status": completion_status,
        "step_count": step + 1,
    }


def tools_node(state: SandboxState) -> Dict[str, Any]:
    """Execution node: runs sandbox tools (and any handoff delegations) selected by the LLM."""
    run_id = state.get("run_id", "default_run")
    last_message = state["messages"][-1]
    tool_messages: List[ToolMessage] = []
    tool_results = list(state.get("tool_results", []))

    if not getattr(last_message, "tool_calls", None):
        return {"messages": []}

    tool_map = {t.name: t for t in _tools_for(state)}

    for tc in last_message.tool_calls:
        if async_agent_manager.is_cancelled(run_id):
            break

        t_name = tc.get("name")
        t_args = tc.get("args", {})
        t_id = tc.get("id", f"call_{int(time.time() * 1000)}")

        if t_name == "finish_sandbox_task":
            continue

        async_agent_manager.set_state(run_id, AgentRunState.RUNNING, f"Executing {t_name}")
        t_start = time.time()
        if t_name in tool_map:
            try:
                output_str = str(tool_map[t_name].invoke(t_args))
            except Exception as exc:
                output_str = f"Tool execution note: {exc}"
        else:
            output_str = f"Unknown tool '{t_name}'"
        dur_ms = int((time.time() - t_start) * 1000)

        mapped_id, mapped_name = TOOL_DISPLAY_MAP.get(t_name, (t_name, t_name))
        # Distinguish "the tool ran" from "the tool found something" instead of
        # hardcoding success regardless of actual output content.
        result_status = "error" if output_str.lower().startswith(("error", "tool execution note:")) else "success"
        tool_results.append({
            "toolId": mapped_id,
            "toolName": mapped_name,
            "status": result_status,
            "executionTimeMs": max(dur_ms, 25),
            "data": {"output": output_str[:800]},
        })
        # Emit a timing event per tool call so the frontend's live activity
        # timeline can show each real step (not just the browser agent).
        async_agent_manager.log_timing(run_id, f"tool_{t_name}", dur_ms, tool=mapped_name)
        tool_messages.append(ToolMessage(content=output_str, tool_call_id=t_id))

    return {"messages": tool_messages, "tool_results": tool_results}


def should_continue(state: SandboxState) -> str:
    """Conditional edge: checks task_complete flag and iteration caps."""
    if state.get("task_complete"):
        return END
    if state.get("step_count", 0) >= MAX_ITERATIONS:
        return END

    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        non_finish = [tc for tc in last_msg.tool_calls if tc.get("name") != "finish_sandbox_task"]
        return "tools" if non_finish else END
    return END


def build_sandbox_agent_graph() -> Any:
    """Build and compile the LangGraph StateGraph workflow for the Sandbox Agent."""
    workflow = StateGraph(SandboxState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    return workflow.compile()


sandbox_agent_graph = build_sandbox_agent_graph()


def run_sandbox_agent(
    user_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: int = 1,
    run_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    **kwargs: Any,
) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Executes the LangGraph Sandbox Agent for arbitrary local code/shell execution tasks.
    Mirrors `browser.langgraph_agent.run_langgraph_browser_agent`'s (prompt/user/run/thread)
    -> (reply, tool_results, provider) contract so the supervisor/executor and other
    agents can call either worker interchangeably.
    """
    actual_run_id = run_id
    if not actual_run_id or not async_agent_manager.get_run(actual_run_id):
        rec = async_agent_manager.create_run(
            user_id=user_id,
            thread_id=thread_id or "default-thread",
            prompt=user_prompt,
            model=os.getenv("DEFAULT_MODEL", settings.default_model),
            run_id=actual_run_id,
        )
        actual_run_id = rec.run_id

    async_agent_manager.set_state(actual_run_id, AgentRunState.RUNNING)

    initial_messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_INSTRUCTION_SANDBOX)]
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
    initial_messages.append(HumanMessage(content=user_prompt))

    initial_state: SandboxState = {
        "messages": initial_messages,
        "task_complete": False,
        "final_result": None,
        "completion_status": "partial",
        "step_count": 0,
        "user_id": user_id,
        "run_id": actual_run_id,
        "thread_id": thread_id or "default-thread",
        "tool_results": [],
    }

    try:
        final_state = sandbox_agent_graph.invoke(initial_state)
        final_output = final_state.get("final_result")
        completion_status_str = final_state.get("completion_status") or "partial"
        if not final_output or len(final_output.strip()) < 5:
            last_msg = final_state["messages"][-1] if final_state["messages"] else None
            final_output = (
                last_msg.content.strip()
                if last_msg and isinstance(last_msg.content, str) and last_msg.content.strip()
                else "Sandbox agent reached its iteration limit without a conclusive result."
            )
            # No explicit finish_sandbox_task verdict was ever produced — do not
            # silently claim COMPLETED for an unverified iteration-limit exit.
            completion_status_str = "partial"
        tool_results_list = final_state.get("tool_results", [])

        # TASK VERIFICATION: cross-check the self-reported status against what the
        # sandbox tools actually produced (e.g. `list 5 files` but only 2 lines were
        # actually read/written) instead of trusting "completed" unconditionally.
        adj_status, adj_verified, adj_requested, verify_note = verify_completion_claim(
            user_prompt=user_prompt, tool_results=tool_results_list, claimed_status=completion_status_str,
        )
        if verify_note:
            final_output = f"{final_output}\n\n_Verification note: {verify_note}_"
        completion_status_str = adj_status

        run_state = STATUS_TO_RUN_STATE.get(completion_status_str, AgentRunState.COMPLETED)
        async_agent_manager.complete_run(
            actual_run_id, final_output, tool_results_list, completion_status=run_state,
            verified_count=adj_verified, requested_count=adj_requested,
        )
        return final_output, tool_results_list, "LangGraph Autonomous Sandbox Agent"

    except LLMTimeoutError as exc:
        async_agent_manager.complete_run(
            actual_run_id, "The sandbox agent timed out waiting for the LLM response.",
            [], error="LLM_TIMEOUT", is_timeout=True, completion_status=AgentRunState.TIMEOUT
        )
        raise exc
    except LLMCancelledError as exc:
        async_agent_manager.complete_run(
            actual_run_id, "Execution was cancelled.", [], error="CANCELLED", completion_status=AgentRunState.CANCELLED
        )
        raise exc
    except Exception as exc:
        async_agent_manager.complete_run(actual_run_id, str(exc), [], error=str(exc), completion_status=AgentRunState.FAILED)
        raise exc
