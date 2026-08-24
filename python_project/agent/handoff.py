"""On-Demand Inter-Agent Handoff Tools.

Exposes each specialist worker agent (Browser, Sandbox, Research) as a callable
LangChain tool so the General agent — or a specialist agent itself — can delegate
a self-contained sub-task to another specialist mid-run, instead of being statically
locked into a single agent for the entire request.

Example: the Browser agent scrapes a table of numbers, then calls
`delegate_to_sandbox_agent("sum column B of this data: ...")` to get an exact
computed result rather than approximating it itself.

A depth-guard (`MAX_DELEGATION_DEPTH`) prevents infinite agent-to-agent recursion
(e.g. Browser -> Sandbox -> Browser -> ...). Depth is tracked per top-level run_id
so any number of *sibling* delegations are allowed, but delegation chains cannot
nest indefinitely.
"""
from typing import Any, Dict, List

from langchain_core.tools import tool

MAX_DELEGATION_DEPTH = 2

# run_id -> current delegation depth. Module-level because tool functions are
# invoked by the LLM with only their declared args — there is no other channel
# to thread call-depth through `.invoke(args)`.
_delegation_depth: Dict[str, int] = {}


def _depth_for(run_id: str) -> int:
    return _delegation_depth.get(run_id, 0)


def _enter_delegation(run_id: str) -> bool:
    """Returns True (and reserves one level) if delegation is still permitted."""
    depth = _depth_for(run_id)
    if depth >= MAX_DELEGATION_DEPTH:
        return False
    _delegation_depth[run_id] = depth + 1
    return True


def _exit_delegation(run_id: str) -> None:
    _delegation_depth[run_id] = max(0, _depth_for(run_id) - 1)


def bind_handoff_tools(run_id: str, user_id: int, thread_id: str) -> List[Any]:
    """
    Build the three cross-agent handoff tools bound to a specific run/user/thread
    context. Call once per agent invocation and append the result to that agent's
    tool list so it can reach the other specialists on demand.
    """

    @tool
    def delegate_to_browser_agent(task: str) -> str:
        """
        Delegate a sub-task to the specialist Browser Agent (navigate pages, click,
        fill forms, extract live page data). Use this when you need real browser/page
        interaction that is outside your own tools.
        Args:
            task: A clear, self-contained description of exactly what the Browser Agent
                should accomplish. It does not see this conversation — include any data
                or context it needs.
        """
        if not _enter_delegation(run_id):
            return "[HANDOFF_DENIED]: Maximum agent delegation depth reached — complete the task with your own tools instead."
        try:
            from browser.langgraph_agent import run_langgraph_browser_agent
            reply, _, _ = run_langgraph_browser_agent(
                user_prompt=task, user_id=user_id, run_id=None, thread_id=thread_id
            )
            return f"[Browser Agent Result]\n{reply}"
        except Exception as exc:
            return f"[Browser Agent Error]: {exc}"
        finally:
            _exit_delegation(run_id)

    @tool
    def delegate_to_sandbox_agent(task: str) -> str:
        """
        Delegate a sub-task to the specialist Sandbox Agent (run shell/Python commands,
        read/write local files). Use this when you need code/command execution that is
        outside your own tools.
        Args:
            task: A clear, self-contained description of exactly what the Sandbox Agent
                should execute or produce. It does not see this conversation — include
                any code/data it needs.
        """
        if not _enter_delegation(run_id):
            return "[HANDOFF_DENIED]: Maximum agent delegation depth reached — complete the task with your own tools instead."
        try:
            from agent.workers.sandbox_agent import run_sandbox_agent
            reply, _, _ = run_sandbox_agent(
                user_prompt=task, user_id=user_id, run_id=None, thread_id=thread_id
            )
            return f"[Sandbox Agent Result]\n{reply}"
        except Exception as exc:
            return f"[Sandbox Agent Error]: {exc}"
        finally:
            _exit_delegation(run_id)

    @tool
    def delegate_to_research_agent(task: str) -> str:
        """
        Delegate a sub-task to the Research Agent (live web search & job-market
        intelligence). Use this when you need fresh information you cannot produce
        yourself.
        Args:
            task: A clear, self-contained research question or search request.
        """
        if not _enter_delegation(run_id):
            return "[HANDOFF_DENIED]: Maximum agent delegation depth reached — answer using information already gathered."
        try:
            from tools.web_search import perform_web_search
            result = perform_web_search(task)
            return f"[Research Agent Result]\n{result.get('formatted', '')}"
        except Exception as exc:
            return f"[Research Agent Error]: {exc}"
        finally:
            _exit_delegation(run_id)

    return [delegate_to_browser_agent, delegate_to_sandbox_agent, delegate_to_research_agent]
