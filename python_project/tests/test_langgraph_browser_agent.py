"""Unit tests for the Stagehand-backed LangGraph Autonomous Browser Agent.

Covers the StateGraph shape (agent/tools loop, `finish_task` terminal tool,
MAX_ITERATIONS guardrail) and the natural-language tool suite
(`browser_navigate`/`browser_act`/`browser_observe`/`browser_extract`), which
replaced the old granular selector-based tools (click_element/type_text/
press_key/get_elements/etc.) now that Stagehand resolves targets internally.
"""
import unittest
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage

from browser.langgraph_agent import (
    BrowserState,
    agent_node,
    tool_node,
    should_continue,
    finish_task,
    browser_navigate,
    browser_act,
    browser_observe,
    browser_extract,
    BROWSER_AGENT_TOOLS,
    browser_agent_graph,
    run_langgraph_browser_agent,
    MAX_ITERATIONS,
    MAX_CONSECUTIVE_NO_PROGRESS,
    STATUS_TO_RUN_STATE,
)
from agent.async_manager import AgentRunState
from langgraph.graph import END


def _make_state(**overrides) -> BrowserState:
    base: BrowserState = {
        "messages": [HumanMessage(content="find jobs")],
        "task_complete": False,
        "final_result": None,
        "completion_status": "partial",
        "verified_count": None,
        "requested_count": None,
        "consecutive_no_progress": 0,
        "step_count": 0,
        "user_id": 1,
        "run_id": "test_run",
        "tool_results": [],
        "thread_id": "test_thread",
    }
    base.update(overrides)
    return base


class TestLangGraphBrowserAgent(unittest.TestCase):
    """Test suite verifying the LangGraph StateGraph, finish_task terminal tool, and guardrails."""

    def test_finish_task_tool_output(self):
        """finish_task simply echoes its `result` back as the terminal Markdown answer."""
        res = finish_task.invoke({"result": "Found 5 verified jobs on portal."})
        self.assertEqual(res, "Found 5 verified jobs on portal.")

    def test_tool_suite_registration(self):
        """Verify the Stagehand-native tool suite is present (no selector-based tools remain)."""
        tool_names = [t.name for t in BROWSER_AGENT_TOOLS]
        required_tools = ["browser_navigate", "browser_act", "browser_observe", "browser_extract", "finish_task"]
        for req in required_tools:
            self.assertIn(req, tool_names, f"Missing required tool: {req}")

        # Old granular selector-based tools must be gone.
        for legacy in ["click_element", "type_text", "press_key", "get_elements", "extract_hyperlinks"]:
            self.assertNotIn(legacy, tool_names)

    def test_browser_navigate_tool_delegates_to_service(self):
        with patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.navigate.return_value.message = "Navigated to https://example.com"
            result = browser_navigate.invoke({"url": "https://example.com"})
            self.assertEqual(result, "Navigated to https://example.com")
            mock_service.navigate.assert_called_once()

    def test_browser_act_tool_surfaces_confirmation_required(self):
        with patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_result = mock_service.act.return_value
            mock_result.status = "confirmation_required"
            mock_result.message = "Sending an email requires approval"
            mock_result.data = {"confirmation_id": "conf-123"}

            result = browser_act.invoke({"instruction": "send this email"})
            self.assertIn("human confirmation", result.lower())
            self.assertIn("conf-123", result)

    def test_browser_observe_and_extract_delegate_to_service(self):
        with patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.observe.return_value.message = "Found 3 buttons"
            mock_service.extract.return_value.message = "Extracted 5 job titles"

            self.assertEqual(browser_observe.invoke({"instruction": "find buttons"}), "Found 3 buttons")
            self.assertEqual(browser_extract.invoke({"instruction": "get job titles"}), "Extracted 5 job titles")

    def test_should_continue_edge_with_finish_task(self):
        """should_continue transitions to END once task_complete is True."""
        state = _make_state(
            messages=[HumanMessage(content="find jobs"), AIMessage(content="done")],
            task_complete=True,
            final_result="5 verified jobs found.",
            step_count=2,
        )
        self.assertEqual(should_continue(state), "end")

    def test_should_continue_edge_with_tool_call(self):
        """should_continue routes to 'tools' when the last AI message emits tool_calls."""
        ai_msg_with_tool = AIMessage(
            content="",
            tool_calls=[{"name": "browser_navigate", "args": {"url": "https://www.naukri.com"}, "id": "c1"}]
        )
        state = _make_state(messages=[HumanMessage(content="find jobs"), ai_msg_with_tool], step_count=1)
        self.assertEqual(should_continue(state), "tools")

    def test_max_iteration_guardrail(self):
        """Reaching MAX_ITERATIONS forces should_continue to return 'end' regardless of tool_calls."""
        state = _make_state(
            messages=[HumanMessage(content="infinite loop attempt")],
            step_count=MAX_ITERATIONS,
        )
        self.assertEqual(should_continue(state), "end")

    def test_agent_node_invokes_llm_and_increments_step_count(self):
        """agent_node should call the LLM once and bump step_count."""
        mock_response = AIMessage(content="Thinking...", tool_calls=[])
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_response), \
             patch("browser.langgraph_agent.get_chat_model"), \
             patch("browser.langgraph_agent.async_agent_manager") as mock_manager:
            mock_manager.is_cancelled.return_value = False
            state = _make_state()
            res = agent_node(state)
            self.assertEqual(res["step_count"], 1)
            self.assertEqual(res["messages"], [mock_response])

    def test_tool_node_intercepts_finish_task(self):
        """tool_node marks task_complete and records final_result when finish_task is invoked."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "finish_task", "args": {"result": "### Final Verified Results Table\n1. Role A"}, "id": "call_99"}]
        )
        with patch("browser.langgraph_agent.async_agent_manager") as mock_manager:
            state = _make_state(messages=[HumanMessage(content="Goal"), ai_msg])
            res = tool_node(state)
            self.assertTrue(res["task_complete"])
            self.assertEqual(res["final_result"], "### Final Verified Results Table\n1. Role A")

    def test_orchestrator_returns_clean_final_data_only(self):
        """run_langgraph_browser_agent should surface only finish_task's result, no raw tool-call chatter."""
        mock_finish_msg = AIMessage(
            content="",
            tool_calls=[{"name": "finish_task", "args": {"result": "Verified the Naukri job listings page loaded successfully"}, "id": "call_1"}]
        )
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_finish_msg), \
             patch("browser.langgraph_agent.get_chat_model"), \
             patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.evaluate_intent.return_value.strategy = "no_action"

            # Prompt intentionally has no "find N items" count so the verification
            # step (tested separately in test_verification.py) has nothing to check
            # against — this test only asserts the output stays clean/unmodified.
            reply, tools, provider = run_langgraph_browser_agent(
                user_prompt="Check whether Naukri.com is reachable",
                user_id=1,
            )
            self.assertEqual(reply, "Verified the Naukri job listings page loaded successfully")
            self.assertNotIn("call_1", reply)
            self.assertNotIn("browser_navigate", reply)
            self.assertEqual(provider, "LangGraph Autonomous Browser Agent (Stagehand)")


class TestStatusTaxonomyFixes(unittest.TestCase):
    """
    Regression tests for the tool-availability / execution / result / task-completion
    conflation bug: a browser tool succeeding must never be silently reported as
    'unavailable', and the run must never be marked COMPLETED unless finish_task
    was actually called with an honest verdict.
    """

    def test_finish_task_carries_structured_status_and_counts(self):
        res = tool_node(_make_state(messages=[HumanMessage(content="go"), AIMessage(
            content="", tool_calls=[{
                "name": "finish_task",
                "args": {"result": "Found 3 of 5 jobs.", "status": "partial", "verified_count": 3, "requested_count": 5},
                "id": "call_1",
            }]
        )]))
        self.assertTrue(res["task_complete"])
        self.assertEqual(res["completion_status"], "partial")
        self.assertEqual(res["verified_count"], 3)
        self.assertEqual(res["requested_count"], 5)

    def test_no_progress_streak_forces_honest_no_results_verdict(self):
        """Repeated empty browser_observe/browser_extract outputs must NOT loop forever
        or get silently replaced by an unrelated fallback — they must force an honest
        NO_RESULTS finish instead."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "browser_observe", "args": {}, "id": "call_x"}]
        )
        with patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.observe.return_value.status = "no_results"
            mock_service.observe.return_value.message = "No actionable elements found."
            state = _make_state(
                messages=[HumanMessage(content="go"), ai_msg],
                consecutive_no_progress=MAX_CONSECUTIVE_NO_PROGRESS - 1,
            )
            res = tool_node(state)
        self.assertTrue(res["task_complete"])
        self.assertEqual(res["completion_status"], "no_results")

    def test_unavailable_tag_short_circuits_as_tool_unavailable(self):
        """A genuinely unavailable browser must be reported as TOOL_UNAVAILABLE,
        not silently retried or reported as generic failure/no-results."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "browser_navigate", "args": {"url": "https://x.com"}, "id": "call_y"}]
        )
        with patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.navigate.return_value.status = "unavailable"
            mock_service.navigate.return_value.message = "Could not launch a managed local browser: no Chromium binary"
            state = _make_state(messages=[HumanMessage(content="go"), ai_msg])
            res = tool_node(state)
        self.assertTrue(res["task_complete"])
        self.assertEqual(res["completion_status"], "tool_unavailable")
        self.assertEqual(STATUS_TO_RUN_STATE["tool_unavailable"], AgentRunState.TOOL_UNAVAILABLE)

    def test_run_langgraph_browser_agent_does_not_fabricate_result_when_finish_task_never_called(self):
        """
        THE ROOT-CAUSE REGRESSION TEST: if the graph exhausts its loop without the
        LLM ever calling finish_task, the agent must NOT silently substitute an
        unrelated fresh web_search/job-search result and report it as verified —
        it must honestly report an unverified/partial outcome instead.
        """
        # LLM never emits a finish_task tool call and keeps "thinking" with no tool
        # calls at all (so should_continue naturally routes straight to END).
        mock_response = AIMessage(content="I looked at the page.", tool_calls=[])
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_response), \
             patch("browser.langgraph_agent.get_chat_model"), \
             patch("browser.langgraph_agent.browser_service") as mock_service, \
             patch("tools.web_search.perform_web_search") as mock_web_search:
            mock_service.evaluate_intent.return_value.strategy = "no_action"

            reply, tools, provider = run_langgraph_browser_agent(
                user_prompt="Find 5 latest jobs on Naukri.com in the last 24 hours",
                user_id=1,
            )

            # The old bug called a hardcoded job-search fallback/perform_web_search as a silent
            # substitute "verified" result — that must never happen now.
            mock_web_search.assert_not_called()
            self.assertIn("unable to complete or verify", reply.lower())

    def test_complete_run_receives_non_completed_status_on_unverified_exit(self):
        """The async run record must reflect PARTIAL/FAILED, never a blanket COMPLETED,
        when finish_task was never called."""
        mock_response = AIMessage(content="", tool_calls=[])
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_response), \
             patch("browser.langgraph_agent.get_chat_model"), \
             patch("browser.langgraph_agent.browser_service") as mock_service, \
             patch("browser.langgraph_agent.async_agent_manager") as mock_manager:
            mock_service.evaluate_intent.return_value.strategy = "no_action"
            mock_manager.get_run.return_value = None
            mock_manager.create_run.return_value.run_id = "run-xyz"
            mock_manager.is_cancelled.return_value = False

            run_langgraph_browser_agent(user_prompt="Find jobs", user_id=1)

            complete_call = mock_manager.complete_run.call_args
            self.assertIn("completion_status", complete_call.kwargs)
            self.assertNotEqual(complete_call.kwargs["completion_status"], AgentRunState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
