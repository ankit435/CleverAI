"""Unit tests for browser/service.py's `act()` auto-recovery behavior (item 7):
when a browser_act call fails, it must automatically re-scan the page via
observe() once and surface fresh candidate elements to help the agent retry
with a more precise instruction, instead of just returning a bare failure.
"""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from browser.service import BrowserService


def _run_coro_now(coro_factory):
    """Stand-in for async_worker.run: executes the coroutine synchronously."""
    return asyncio.new_event_loop().run_until_complete(coro_factory())


class TestBrowserActAutoRecovery(unittest.TestCase):
    def _make_fake_session(self, act_success: bool, observe_candidates=None):
        session = MagicMock()
        session.is_connected = True
        session.get_page_for_thread = AsyncMock(return_value=MagicMock(
            url=AsyncMock(return_value="https://example.com"),
            title=AsyncMock(return_value="Example"),
        ))

        act_result = SimpleNamespace(data=SimpleNamespace(success=act_success, message="act outcome"))
        session.stagehand.act = AsyncMock(return_value=act_result)

        observe_items = observe_candidates or []
        observe_result = SimpleNamespace(data=[
            SimpleNamespace(description=d, method=m) for d, m in observe_items
        ])
        session.stagehand.observe = AsyncMock(return_value=observe_result)
        return session

    def test_successful_act_does_not_trigger_recovery_observe(self):
        service = BrowserService()
        fake_session = self._make_fake_session(act_success=True)
        with patch.object(service.session_manager, "get_or_create", return_value=fake_session), \
             patch("browser.service.async_worker") as mock_worker:
            mock_worker.run.side_effect = _run_coro_now
            result = service.act(user_id=1, instruction="click submit")

        self.assertEqual(result.status, "success")
        fake_session.stagehand.observe.assert_not_called()
        self.assertNotIn("AUTO-RECOVERY", result.message)

    def test_failed_act_triggers_recovery_observe_and_appends_candidates(self):
        service = BrowserService()
        fake_session = self._make_fake_session(
            act_success=False,
            observe_candidates=[("Sign in button", "click"), ("Search box", "type")],
        )
        with patch.object(service.session_manager, "get_or_create", return_value=fake_session), \
             patch("browser.service.async_worker") as mock_worker:
            mock_worker.run.side_effect = _run_coro_now
            result = service.act(user_id=1, instruction="click a nonexistent button")

        self.assertEqual(result.status, "error")
        fake_session.stagehand.observe.assert_called_once()
        self.assertIn("AUTO-RECOVERY", result.message)
        self.assertIn("Sign in button", result.message)
        self.assertIn("Search box", result.message)
        self.assertIsNotNone(result.data)
        self.assertEqual(len(result.data["recovery_observation"]), 2)

    def test_failed_act_when_recovery_observe_itself_fails_does_not_mask_original_error(self):
        service = BrowserService()
        fake_session = self._make_fake_session(act_success=False)
        fake_session.stagehand.observe = AsyncMock(side_effect=RuntimeError("observe also broken"))
        with patch.object(service.session_manager, "get_or_create", return_value=fake_session), \
             patch("browser.service.async_worker") as mock_worker:
            mock_worker.run.side_effect = _run_coro_now
            result = service.act(user_id=1, instruction="click a nonexistent button")

        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "act outcome")  # original message untouched

    def test_act_result_includes_timing_breakdown(self):
        """Item 3: act() must report real sub-span timing, not just one opaque duration_ms."""
        service = BrowserService()
        fake_session = self._make_fake_session(act_success=True)
        with patch.object(service.session_manager, "get_or_create", return_value=fake_session), \
             patch("browser.service.async_worker") as mock_worker:
            mock_worker.run.side_effect = _run_coro_now
            result = service.act(user_id=1, instruction="click submit")

        self.assertIsNotNone(result.timing_breakdown)
        self.assertIn("stagehand_reasoning_ms", result.timing_breakdown)
        self.assertIn("session_acquisition_ms", result.timing_breakdown)


if __name__ == "__main__":
    unittest.main()
