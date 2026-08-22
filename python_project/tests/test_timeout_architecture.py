"""Comprehensive Tests for the Async Agent Run Lifecycle, Component Timeouts & Cancellation."""
import unittest
import time
import asyncio
from unittest.mock import MagicMock, patch

from agent.async_manager import (
    async_agent_manager, AgentRunState, AgentRunRecord, ErrorType,
    HTTP_REQUEST_TIMEOUT, LLM_REQUEST_TIMEOUT, BROWSER_ACTION_TIMEOUT,
    BROWSER_NAVIGATION_TIMEOUT, INDIVIDUAL_TOOL_TIMEOUT, AGENT_TOTAL_RUN_TIMEOUT
)
from models import invoke_llm_with_diagnostics, LLMTimeoutError, LLMCancelledError
from tools.executor import execute_tool_calling_flow

class TestTimeoutArchitecture(unittest.TestCase):

    def setUp(self):
        # Clean state for each test
        async_agent_manager._runs.clear()
        async_agent_manager._cancellation_events.clear()
        async_agent_manager._queues.clear()

    # ==========================================================
    # 1. Component Timeout Policy Separation
    # ==========================================================
    def test_timeout_policy_separation(self):
        self.assertEqual(HTTP_REQUEST_TIMEOUT, 15.0)
        self.assertEqual(LLM_REQUEST_TIMEOUT, 30.0)
        self.assertEqual(BROWSER_ACTION_TIMEOUT, 15.0)
        self.assertEqual(BROWSER_NAVIGATION_TIMEOUT, 25.0)
        self.assertEqual(INDIVIDUAL_TOOL_TIMEOUT, 20.0)
        self.assertEqual(AGENT_TOTAL_RUN_TIMEOUT, 300.0)
        self.assertNotEqual(HTTP_REQUEST_TIMEOUT, AGENT_TOTAL_RUN_TIMEOUT)
        self.assertNotEqual(LLM_REQUEST_TIMEOUT, BROWSER_NAVIGATION_TIMEOUT)

    # ==========================================================
    # 2. Async Agent Run Lifecycle & States
    # ==========================================================
    def test_agent_run_lifecycle_and_states(self):
        record = async_agent_manager.create_run(
            user_id=101,
            thread_id="thread-test-1",
            prompt="Find laptops on shopping site",
            model="test-model"
        )
        self.assertEqual(record.status, AgentRunState.QUEUED)
        self.assertEqual(record.user_id, 101)

        # State transitions
        async_agent_manager.set_state(record.run_id, AgentRunState.RUNNING, "Starting agent")
        self.assertEqual(async_agent_manager.get_run(record.run_id).status, AgentRunState.RUNNING)

        async_agent_manager.set_state(record.run_id, AgentRunState.WAITING_FOR_LLM, "Calling NIM")
        self.assertEqual(async_agent_manager.get_run(record.run_id).status, AgentRunState.WAITING_FOR_LLM)

        async_agent_manager.set_state(record.run_id, AgentRunState.WAITING_FOR_BROWSER, "Clicking Search")
        self.assertEqual(async_agent_manager.get_run(record.run_id).status, AgentRunState.WAITING_FOR_BROWSER)

        async_agent_manager.complete_run(
            record.run_id,
            response_text="Here are the laptops found.",
            tool_results=[{"toolId": "web_search", "status": "success"}]
        )
        completed = async_agent_manager.get_run(record.run_id)
        self.assertEqual(completed.status, AgentRunState.COMPLETED)
        self.assertEqual(completed.final_response, "Here are the laptops found.")
        self.assertGreater(completed.execution_time_ms, -1)

    # ==========================================================
    # 3. Cancellation Handling & Propagation
    # ==========================================================
    def test_cancellation_propagation(self):
        record = async_agent_manager.create_run(
            user_id=102,
            thread_id="thread-test-2",
            prompt="Long search",
            model="test-model"
        )
        async_agent_manager.set_state(record.run_id, AgentRunState.RUNNING)

        # Cancel active run
        cancelled = async_agent_manager.cancel_run(record.run_id)
        self.assertTrue(cancelled)
        self.assertTrue(async_agent_manager.is_cancelled(record.run_id))
        self.assertEqual(async_agent_manager.get_run(record.run_id).status, AgentRunState.CANCELLED)

        # Attempting LLM invoke on cancelled run must immediately raise LLMCancelledError
        mock_llm = MagicMock()
        with self.assertRaises(LLMCancelledError):
            invoke_llm_with_diagnostics(mock_llm, ["hello"], run_id=record.run_id)

    # ==========================================================
    # 4. Timeout Diagnostics & Bounded Retries
    # ==========================================================
    def test_llm_timeout_diagnostic_and_bounded_retry(self):
        record = async_agent_manager.create_run(
            user_id=103,
            thread_id="thread-test-3",
            prompt="Timeout test",
            model="test-model"
        )

        mock_llm = MagicMock()
        # Mock timeout exception from upstream NIM
        mock_llm.invoke.side_effect = Exception("The operation was aborted due to timeout")

        with self.assertRaises(LLMTimeoutError):
            invoke_llm_with_diagnostics(mock_llm, ["test"], run_id=record.run_id, max_retries=1)

        # Verify diagnostic was logged
        rec = async_agent_manager.get_run(record.run_id)
        self.assertGreaterEqual(len(rec.diagnostics), 1)
        diag = rec.diagnostics[0]
        self.assertEqual(diag.component, "NVIDIA NIM API")
        self.assertEqual(diag.timeout_type, ErrorType.NIM_TIMEOUT.value)
        self.assertEqual(diag.operation, "chat_completion")

    # ==========================================================
    # 5. Non-Retryable Error Handling (No Infinite Loops)
    # ==========================================================
    def test_non_retryable_error_does_not_loop(self):
        record = async_agent_manager.create_run(
            user_id=104,
            thread_id="thread-test-4",
            prompt="Bad auth",
            model="test-model"
        )

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ValueError("401 Unauthorized: Invalid API key")

        with self.assertRaises(ValueError):
            invoke_llm_with_diagnostics(mock_llm, ["test"], run_id=record.run_id, max_retries=1)

        # Exactly 1 attempt should have been made for 401
        self.assertEqual(mock_llm.invoke.call_count, 1)

    # ==========================================================
    # 6. Structured Timing Logs (No Secret Leakage)
    # ==========================================================
    def test_structured_timing_logs(self):
        record = async_agent_manager.create_run(
            user_id=105,
            thread_id="thread-test-5",
            prompt="Timing test",
            model="test-model"
        )
        async_agent_manager.log_timing(record.run_id, "llm_request_started", 0, iteration=1)
        async_agent_manager.log_timing(record.run_id, "llm_request_completed", 420, iteration=1)
        async_agent_manager.log_timing(record.run_id, "browser_action_started", 0, iteration=1, tool="browser_click")
        async_agent_manager.log_timing(record.run_id, "browser_action_completed", 120, iteration=1, tool="browser_click")

        rec = async_agent_manager.get_run(record.run_id)
        event_names = [e.event_name for e in rec.timing_logs]
        self.assertIn("llm_request_started", event_names)
        self.assertIn("llm_request_completed", event_names)
        self.assertIn("browser_action_started", event_names)
        self.assertIn("browser_action_completed", event_names)

        # Verify no token secrets are stored in timing events
        for e in rec.timing_logs:
            self.assertFalse(hasattr(e, "api_key"))
            self.assertFalse(hasattr(e, "authorization"))

    # ==========================================================
    # 7. No Uncontrolled Fallback on LLM Timeout
    # ==========================================================
    def test_no_uncontrolled_fallback_on_llm_timeout(self):
        run_record = async_agent_manager.create_run(
            user_id=106,
            thread_id="thread-test-6",
            prompt="Simple query",
            model="test-model"
        )

        with patch("tools.executor.invoke_llm_with_diagnostics") as mock_invoke:
            mock_invoke.side_effect = LLMTimeoutError("LLM request timed out after 30000ms")

            with self.assertRaises(LLMTimeoutError):
                execute_tool_calling_flow(
                    user_prompt="Simple query",
                    active_plugin_ids=[],
                    run_id=run_record.run_id,
                    user_id=106
                )

        rec = async_agent_manager.get_run(run_record.run_id)
        self.assertEqual(rec.status, AgentRunState.TIMEOUT)


if __name__ == "__main__":
    unittest.main()
