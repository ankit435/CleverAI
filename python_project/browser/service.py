

"""Unified Browser Service Facade (Stagehand-backed).

Sync-callable facade over the async Stagehand session manager: every public
method here submits a coroutine to the single background event-loop thread
(`browser.async_worker`) and blocks until it resolves, so callers elsewhere in
this still-mostly-synchronous codebase (FastAPI routes, LangGraph agent nodes,
`tools/executor.py`) don't need to become `async def` themselves.

This is also where the Human Confirmation Security Gate is enforced: any
`act()` instruction assessed as risky is intercepted *before* Stagehand ever
sees it, and only proceeds once a human approves it via `resolve_confirmation`.
"""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from browser.async_worker import async_worker
from browser.policy import browser_policy
from browser.schema import (
    ActionResult, BrowserMode, BrowserStatus, CONFIRMATION_EXPIRY_SECONDS,
    ConfirmationRequest, PolicyDecision, TabInfo,
)
from browser.security_manager import security_manager
from browser.session_manager import browser_session_manager


class BrowserService:
    """Production-grade Browser Service: Stagehand session lifecycle + security gate."""

    def __init__(self) -> None:
        self.session_manager = browser_session_manager
        self.policy = browser_policy

    # ------------------------------------------------------------------ #
    # Intent / policy
    # ------------------------------------------------------------------ #
    def evaluate_intent(self, user_prompt: str, user_id: int = 1) -> PolicyDecision:
        status = self.get_status(user_id=user_id)
        return self.policy.evaluate_request(user_prompt, status)

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #
    def connect(
        self, user_id: int = 1, mode: BrowserMode = BrowserMode.EXISTING_CDP, cdp_url: str = "http://127.0.0.1:9222"
    ) -> Tuple[bool, str, BrowserStatus]:
        async def _do():
            session = self.session_manager.get_or_create(user_id)
            try:
                if mode == BrowserMode.MANAGED_BROWSER:
                    await session.launch_managed()
                else:
                    await session.connect_existing(cdp_url=cdp_url)
                return True, "Connected successfully.", await session.get_status()
            except Exception as exc:
                return False, f"Connection failed: {exc}", await session.get_status()

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return False, f"Connection failed: {exc}", BrowserStatus(connected=False, user_id=user_id)

    def disconnect(self, user_id: int = 1) -> Tuple[bool, str]:
        async def _do():
            session = self.session_manager.get(user_id)
            if session:
                await session.close()
                return True, "Disconnected from browser successfully."
            return True, "No active browser session was connected."

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return False, f"Disconnect error: {exc}"

    def reap_idle_sessions(self, idle_timeout_seconds: float = 300.0) -> int:
        """Close inactive browser sessions exceeding idle timeout to save resources."""
        async def _do():
            return await self.session_manager.reap_idle_sessions(idle_timeout_seconds)

        try:
            return async_worker.run(_do)
        except Exception:
            return 0

    def get_status(self, user_id: int = 1) -> BrowserStatus:
        async def _do():
            session = self.session_manager.get(user_id)
            if not session:
                return BrowserStatus(connected=False, user_id=user_id)
            return await session.get_status()

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return BrowserStatus(connected=False, user_id=user_id, error=str(exc))

    # ------------------------------------------------------------------ #
    # Tabs
    # ------------------------------------------------------------------ #
    def list_tabs(self, user_id: int = 1) -> List[TabInfo]:
        async def _do():
            session = self.session_manager.get(user_id)
            if not session or not session.is_connected:
                return []
            return await session.list_tabs()

        try:
            return async_worker.run(_do)
        except Exception:
            return []

    def select_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str, Optional[TabInfo]]:
        async def _do():
            session = self.session_manager.get(user_id)
            if not session or not session.is_connected:
                return False, "Browser not connected", None
            pages = await session.browser.context.pages()
            target = next((p for p in pages if p.page_id == tab_id), None)
            if not target:
                return False, f"Tab '{tab_id}' not found", None
            await session.browser.context.set_active_page(target)
            tabs = await session.list_tabs()
            tab = next((t for t in tabs if t.id == tab_id), None)
            return True, "Tab switched.", tab

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return False, f"Tab selection failed: {exc}", None

    def open_new_tab(self, user_id: int, url: str = "about:blank") -> Tuple[bool, str, Optional[TabInfo]]:
        async def _do():
            session = self.session_manager.get_or_create(user_id)
            if not session.is_connected:
                await session.launch_managed()
            clean_url = security_manager.normalize_url(url)
            ok, err = security_manager.validate_url(clean_url) if clean_url != "about:blank" else (True, None)
            if not ok:
                return False, f"Blocked: {err}", None
            page = await session.browser.context.new_page(clean_url if clean_url != "about:blank" else None)
            title = await page.title()
            return True, "New tab opened.", TabInfo(id=page.page_id, title=title or "Untitled", url=clean_url, active=True)

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return False, f"Open tab failed: {exc}", None

    def close_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str]:
        async def _do():
            session = self.session_manager.get(user_id)
            if not session or not session.is_connected:
                return False, "Browser not connected"
            pages = await session.browser.context.pages()
            target = next((p for p in pages if p.page_id == tab_id), None)
            if not target:
                return False, f"Tab '{tab_id}' not found"
            await target.close()
            return True, "Tab closed."

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return False, f"Close tab error: {exc}"

    # ------------------------------------------------------------------ #
    # Core Stagehand actions: navigate / act / observe / extract
    # ------------------------------------------------------------------ #
    def navigate(self, user_id: int, url: str, thread_id: Optional[str] = None) -> ActionResult:
        async def _do():
            start = time.time()
            clean_url = security_manager.normalize_url(url)
            ok, err = security_manager.validate_url(clean_url)
            if not ok:
                return ActionResult(action="navigate", status="error", message=f"Navigation blocked: {err}", error="SSRF_BLOCKED")

            session = self.session_manager.get_or_create(user_id)
            if not session.is_connected:
                await session.launch_managed()
            page = await session.get_page_for_thread(thread_id)
            await page.goto(clean_url)
            title = await page.title()
            final_url = await page.url()
            return ActionResult(
                action="navigate", status="success", message=f"Navigated to {final_url}",
                duration_ms=int((time.time() - start) * 1000), current_url=final_url, current_title=title,
            )

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return ActionResult(action="navigate", status="error", message=f"Navigation failed: {exc}", error=str(exc))

    def act(self, user_id: int, instruction: str, confirmed: bool = False, thread_id: Optional[str] = None) -> ActionResult:
        """Execute a natural-language browser action via Stagehand's `act()`."""
        # 1. Human Confirmation Security Gate — evaluated before ever touching Stagehand.
        risk_level, requires_confirm, reason = security_manager.assess_instruction_risk(instruction)
        if requires_confirm and not confirmed:
            session = self.session_manager.get_or_create(user_id)
            confirm_id = str(uuid.uuid4())
            expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + CONFIRMATION_EXPIRY_SECONDS))
            confirm_req = ConfirmationRequest(
                id=confirm_id, user_id=user_id, instruction=instruction,
                reason=reason or "High-risk browser action requires explicit authorization",
                risk_level=risk_level, status="pending", expires_at=expires_at,
            )
            session.pending_confirmations[confirm_id] = confirm_req
            session.confirmation_threads[confirm_id] = thread_id
            return ActionResult(
                action="act", status="confirmation_required",
                message=f"⚠️ Human Confirmation Required: {reason}. Approve action to proceed.",
                confirmation=confirm_req, data={"confirmation_id": confirm_id, "reason": reason, "risk_level": risk_level},
            )

        async def _do():
            start = time.time()
            session = self.session_manager.get_or_create(user_id)
            if not session.is_connected:
                await session.launch_managed()
            page = await session.get_page_for_thread(thread_id)
            result = await session.stagehand.act(instruction, page=page)
            url = await page.url() if page else None
            title = await page.title() if page else None
            return ActionResult(
                action="act", status="success" if result.data.success else "error",
                message=result.data.message, duration_ms=int((time.time() - start) * 1000),
                current_url=url, current_title=title,
            )

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return ActionResult(action="act", status="error", message=f"Action failed: {exc}", error=str(exc))

    def observe(self, user_id: int, instruction: Optional[str] = None, thread_id: Optional[str] = None) -> ActionResult:
        """Discover available actions/elements on the current page via Stagehand's `observe()`."""
        async def _do():
            start = time.time()
            session = self.session_manager.get_or_create(user_id)
            if not session.is_connected:
                await session.launch_managed()
            page = await session.get_page_for_thread(thread_id)
            result = await session.stagehand.observe(instruction, page=page)
            candidates = [
                {"description": getattr(a, "description", "") or "", "method": getattr(a, "method", "") or ""}
                for a in result.data
            ]
            summary = "\n".join(f"- {c['description']} ({c['method']})" for c in candidates) or "No actionable elements found."
            return ActionResult(
                action="observe", status="success", message=summary,
                duration_ms=int((time.time() - start) * 1000), data={"candidates": candidates},
            )

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return ActionResult(action="observe", status="error", message=f"Observe failed: {exc}", error=str(exc))

    def extract(self, user_id: int, instruction: str, thread_id: Optional[str] = None) -> ActionResult:
        """Pull structured/free-text data from the current page via Stagehand's `extract()`."""
        async def _do():
            start = time.time()
            session = self.session_manager.get_or_create(user_id)
            if not session.is_connected:
                await session.launch_managed()
            result = await session.stagehand.extract(instruction)
            raw_text = getattr(result.data, "extraction", str(result.data))
            page = await session.browser.context.active_page()
            url = await page.url() if page else None
            sanitized = security_manager.wrap_untrusted_content(raw_text, url or "unknown")
            return ActionResult(
                action="extract", status="success", message=sanitized,
                duration_ms=int((time.time() - start) * 1000), current_url=url, data={"raw": raw_text},
            )

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return ActionResult(action="extract", status="error", message=f"Extraction failed: {exc}", error=str(exc))

    def screenshot(self, user_id: int) -> ActionResult:
        async def _do():
            start = time.time()
            session = self.session_manager.get(user_id)
            if not session or not session.is_connected:
                return ActionResult(action="screenshot", status="error", message="Browser not connected.", error="BROWSER_NOT_CONNECTED")
            page = await session.browser.context.active_page()
            if page is None:
                return ActionResult(action="screenshot", status="error", message="No active page.", error="NO_ACTIVE_PAGE")
            data = await page.screenshot()
            return ActionResult(
                action="screenshot", status="success", message="Screenshot captured.",
                duration_ms=int((time.time() - start) * 1000), data={"png_bytes_len": len(data)},
            )

        try:
            return async_worker.run(_do)
        except Exception as exc:
            return ActionResult(action="screenshot", status="error", message=f"Screenshot failed: {exc}", error=str(exc))

    # ------------------------------------------------------------------ #
    # Confirmation resolution
    # ------------------------------------------------------------------ #
    def resolve_confirmation(self, user_id: int, confirmation_id: str, approved: bool) -> ActionResult:
        session = self.session_manager.get(user_id)
        if not session or confirmation_id not in session.pending_confirmations:
            return ActionResult(action="confirm", status="error", message=f"Confirmation request '{confirmation_id}' not found or expired.", error="CONFIRMATION_NOT_FOUND")

        confirm_req = session.pending_confirmations.pop(confirmation_id)
        thread_id = session.confirmation_threads.pop(confirmation_id, None)
        if not approved:
            confirm_req.status = "rejected"
            return ActionResult(action=confirm_req.instruction, status="error", message="Action was rejected by user.", error="CONFIRMATION_REJECTED", confirmation=confirm_req)

        confirm_req.status = "approved"
        return self.act(user_id=user_id, instruction=confirm_req.instruction, confirmed=True, thread_id=thread_id)


browser_service = BrowserService()

