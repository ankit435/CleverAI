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
)
from langgraph.graph import END


def _make_state(**overrides) -> BrowserState:
    base: BrowserState = {
        "messages": [HumanMessage(content="find jobs")],
        "task_complete": False,
        "final_result": None,
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
            tool_calls=[{"name": "finish_task", "args": {"result": "Verified 5 Job Openings on Naukri within 24h"}, "id": "call_1"}]
        )
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_finish_msg), \
             patch("browser.langgraph_agent.get_chat_model"), \
             patch("browser.langgraph_agent.browser_service") as mock_service:
            mock_service.evaluate_intent.return_value.strategy = "no_action"

            reply, tools, provider = run_langgraph_browser_agent(
                user_prompt="Find 5 latest jobs on Naukri.com",
                user_id=1,
            )
            self.assertEqual(reply, "Verified 5 Job Openings on Naukri within 24h")
            self.assertNotIn("call_1", reply)
            self.assertNotIn("browser_navigate", reply)
            self.assertEqual(provider, "LangGraph Autonomous Browser Agent (Stagehand)")


if __name__ == "__main__":
    unittest.main()
