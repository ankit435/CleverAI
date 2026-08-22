"""Unit tests for LangGraph Autonomous Browser Agent Architecture."""
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from browser.langgraph_agent import (
    BrowserState,
    build_browser_agent_graph,
    agent_node,
    tools_node,
    should_continue,
    finish_task,
    navigate_browser,
    extract_text,
    get_elements,
    click_element,
    type_text,
    press_key,
    wait_for_selector,
    extract_hyperlinks,
    screenshot,
    ALL_LANGGRAPH_TOOLS,
    run_langgraph_browser_agent,
    MAX_ITERATIONS
)
from langgraph.graph import END

class TestLangGraphBrowserAgent(unittest.TestCase):
    """Test suite verifying LangGraph StateGraph, finish_task terminal tool, and guardrails."""

    def test_finish_task_tool_output(self):
        """Test that finish_task formats the terminal signal correctly."""
        res = finish_task.invoke({"result": "Found 5 verified jobs on portal."})
        self.assertIn("[TASK_COMPLETED]", res)
        self.assertIn("Found 5 verified jobs on portal.", res)

    def test_tool_suite_registration(self):
        """Verify all required Playwright browser tools are present and bound."""
        tool_names = [t.name for t in ALL_LANGGRAPH_TOOLS]
        required_tools = [
            "navigate_browser", "extract_text", "get_elements", "click_element",
            "type_text", "press_key", "wait_for_selector", "extract_hyperlinks",
            "screenshot", "web_search", "find_and_rank_jobs", "calculate",
            "code_interpreter", "finish_task"
        ]
        for req in required_tools:
            self.assertIn(req, tool_names, f"Missing required tool: {req}")

    def test_should_continue_edge_with_finish_task(self):
        """Verify should_continue transitions to END when finish_task is called or task_complete is True."""
        state_complete: BrowserState = {
            "messages": [HumanMessage(content="find jobs"), AIMessage(content="done")],
            "task_complete": True,
            "final_result": "5 verified jobs found.",
            "step_count": 2,
            "user_id": 1,
            "run_id": "test_run",
            "tool_results": [],
            "consecutive_navigates": 0
        }
        self.assertEqual(should_continue(state_complete), END)

    def test_should_continue_edge_with_tool_call(self):
        """Verify should_continue routes to 'tools' when active browser actions are emitted."""
        ai_msg_with_tool = AIMessage(
            content="",
            tool_calls=[{"name": "navigate_browser", "args": {"url": "https://www.naukri.com"}, "id": "c1"}]
        )
        state_active: BrowserState = {
            "messages": [HumanMessage(content="find jobs"), ai_msg_with_tool],
            "task_complete": False,
            "final_result": None,
            "step_count": 1,
            "user_id": 1,
            "run_id": "test_run",
            "tool_results": [],
            "consecutive_navigates": 0
        }
        self.assertEqual(should_continue(state_active), "tools")

    def test_max_iteration_guardrail(self):
        """Verify that reaching MAX_ITERATIONS forces transition to END."""
        state_capped: BrowserState = {
            "messages": [HumanMessage(content="infinite loop attempt")],
            "task_complete": False,
            "final_result": None,
            "step_count": MAX_ITERATIONS,
            "user_id": 1,
            "run_id": "test_run",
            "tool_results": [],
            "consecutive_navigates": 0
        }
        self.assertEqual(should_continue(state_capped), END)

    def test_agent_node_intercepts_finish_task(self):
        """Test that agent_node extracts final_result directly from finish_task tool call."""
        mock_response = AIMessage(
            content="",
            tool_calls=[{"name": "finish_task", "args": {"result": "### Final Verified Results Table\n1. Role A"}, "id": "call_99"}]
        )
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_response):
            state: BrowserState = {
                "messages": [HumanMessage(content="Goal")],
                "task_complete": False,
                "final_result": None,
                "step_count": 0,
                "user_id": 1,
                "run_id": "test_run",
                "tool_results": [],
                "consecutive_navigates": 0
            }
            res = agent_node(state)
            self.assertTrue(res["task_complete"])
            self.assertEqual(res["final_result"], "### Final Verified Results Table\n1. Role A")
            self.assertEqual(res["step_count"], 1)

    def test_orchestrator_returns_clean_final_data_only(self):
        """Test that run_langgraph_browser_agent returns only the structured output."""
        mock_finish_msg = AIMessage(
            content="",
            tool_calls=[{"name": "finish_task", "args": {"result": "Verified 5 Job Openings on Naukri within 24h"}, "id": "call_1"}]
        )
        with patch("browser.langgraph_agent.invoke_llm_with_diagnostics", return_value=mock_finish_msg):
            reply, tools, provider = run_langgraph_browser_agent(
                user_prompt="Find 5 latest jobs on Naukri.com",
                user_id=1
            )
            self.assertEqual(reply, "Verified 5 Job Openings on Naukri within 24h")
            self.assertNotIn("call_1", reply)
            self.assertNotIn("navigate_browser", reply)
            self.assertEqual(provider, "LangGraph Autonomous Browser Agent")

if __name__ == "__main__":
    unittest.main()
