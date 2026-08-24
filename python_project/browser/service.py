"""Unified Browser Service Facade: Integrates Policy Engine, Session Management, Security, Page Automation, and Thread Affinity Worker."""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, PageSnapshot, ActionResult,
    ConfirmationRequest, RiskLevel, PolicyDecision, PolicyStrategy
)
from browser.policy import browser_policy
from browser.session_manager import browser_session_manager, UserBrowserSession
from browser.page_controller import PageController
from browser.security_manager import security_manager
from browser.playwright_worker import playwright_worker

CONFIRMATION_EXPIRY_SECONDS = 300  # 5 minutes

class BrowserService:
    """Production-grade Browser Service with Autonomous Policy, Multi-User Isolation, and Thread Affinity."""

    def __init__(self):
        self.session_manager = browser_session_manager
        self.policy = browser_policy
        self.worker = playwright_worker

    def evaluate_intent(self, user_prompt: str, user_id: int = 1) -> PolicyDecision:
        """Evaluate whether a user prompt needs browser and what strategy to apply."""
        status = self.get_status(user_id=user_id)
        return self.policy.evaluate_request(user_prompt, status)

    def connect(
        self,
        user_id: int = 1,
        mode: BrowserMode = BrowserMode.EXISTING_CDP,
        cdp_url: str = "http://127.0.0.1:9222"
    ) -> Tuple[bool, str, BrowserStatus]:
        """Connect to existing Chrome/Edge or launch managed browser inside dedicated worker thread."""
        def _task():
            if mode == BrowserMode.MANAGED_BROWSER:
                ok, msg, _ = self.session_manager.launch_managed_browser(user_id=user_id)
            else:
                ok, msg, _ = self.session_manager.connect_existing_browser(user_id=user_id, cdp_url=cdp_url)
            return ok, msg, self._get_status_sync(user_id)

        try:
            return self.worker.run(_task)
        except Exception as e:
            return False, f"Connection failed: {str(e)}", self.get_status(user_id)

    def disconnect(self, user_id: int = 1) -> Tuple[bool, str]:
        """Cleanly disconnect user browser session."""
        def _task():
            session = self.session_manager.get_session(user_id)
            if session:
                session.disconnect()
                return True, "Disconnected from browser successfully."
            return True, "No active browser session was connected."

        try:
            return self.worker.run(_task)
        except Exception as e:
            return False, f"Disconnect error: {str(e)}"

    def _get_status_sync(self, user_id: int = 1) -> BrowserStatus:
        return self.session_manager.get_status(user_id=user_id)

    def get_status(self, user_id: int = 1) -> BrowserStatus:
        """Return connectivity, active tabs, and metadata for user."""
        try:
            return self.worker.run(lambda: self._get_status_sync(user_id))
        except Exception:
            return self._get_status_sync(user_id)

    def list_tabs(self, user_id: int = 1) -> List[TabInfo]:
        """List open tabs in user's browser."""
        def _task():
            session = self.session_manager.get_session(user_id)
            if not session or not session.context:
                return []
            return session.tab_manager.list_tabs(session.context)

        try:
            return self.worker.run(_task)
        except Exception:
            return []

    def get_active_tab(self, user_id: int = 1) -> Optional[TabInfo]:
        """Get currently active tab for user."""
        tabs = self.list_tabs(user_id)
        return next((t for t in tabs if t.active), tabs[0] if tabs else None)

    def select_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str, Optional[TabInfo]]:
        """Switch active tab in user's browser."""
        def _task():
            session = self.session_manager.get_session(user_id)
            if not session or not session.context:
                return False, "Browser not connected", None
            return session.tab_manager.select_tab(session.context, tab_id)

        try:
            return self.worker.run(_task)
        except Exception as e:
            return False, f"Tab selection failed: {str(e)}", None

    def open_new_tab(self, user_id: int, url: str = "about:blank") -> Tuple[bool, str, Optional[TabInfo]]:
        """Open a new tab in user's browser."""
        def _task():
            session = self.session_manager.get_session(user_id)
            if not session or not session.context:
                self.session_manager.launch_managed_browser(user_id)
                session = self.session_manager.get_session(user_id)
                if not session or not session.context:
                    return False, "Failed to launch browser", None

            return session.tab_manager.open_new_tab(session.context, url)

        try:
            return self.worker.run(_task)
        except Exception as e:
            return False, f"Open tab failed: {str(e)}", None

    def close_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str]:
        """Close specific tab in user's browser."""
        def _task():
            session = self.session_manager.get_session(user_id)
            if not session or not session.context:
                return False, "Browser not connected"
            return session.tab_manager.close_tab(session.context, tab_id)

        try:
            return self.worker.run(_task)
        except Exception as e:
            return False, f"Close tab error: {str(e)}"

    def snapshot(self, user_id: int = 1, tab_id: Optional[str] = None) -> ActionResult:
        """Capture DOM accessibility tree and interactive elements."""
        def _task():
            start = time.time()
            session = self.session_manager.get_session(user_id)

            if not session or not session.is_connected or not session.context:
                ok, msg, session = self.session_manager.launch_managed_browser(user_id)
                if not ok or not session or not session.context:
                    return ActionResult(
                        action="snapshot",
                        status="error",
                        duration_ms=int((time.time() - start) * 1000),
                        message="Browser not connected. Start Chrome with remote debugging or launch managed browser.",
                        error="BROWSER_NOT_CONNECTED"
                    )

            page, err = session.tab_manager.get_page_by_id(session.context, tab_id)
            if err or not page:
                return ActionResult(
                    action="snapshot",
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=err or "Page not available",
                    error=err
                )

            active_id = tab_id or session.tab_manager._active_tab_id or "tab_1"
            page_snap = PageController.capture_snapshot(page, active_id)
            duration_ms = int((time.time() - start) * 1000)

            return ActionResult(
                action="snapshot",
                status="success",
                duration_ms=duration_ms,
                message=f"Snapshot captured for '{page_snap.title}' ({len(page_snap.elements)} interactive elements)",
                current_url=page_snap.url,
                current_title=page_snap.title,
                snapshot=page_snap,
                data={"formatted_snapshot": page_snap.formatted_snapshot}
            )

        try:
            return self.worker.run(_task)
        except Exception as e:
            return ActionResult(
                action="snapshot",
                status="error",
                duration_ms=0,
                message=f"Snapshot failed: {str(e)}",
                error=str(e)
            )

    def execute_action(
        self,
        user_id: int,
        action: str,
        selector: Optional[str] = None,
        text_input: Optional[str] = None,
        url: Optional[str] = None,
        element_id: Optional[Any] = None,
        role: Optional[str] = None,
        name: Optional[str] = None,
        coordinates: Optional[Tuple[float, float]] = None,
        key: Optional[str] = None,
        direction: str = "down",
        pixels: int = 500,
        tab_id: Optional[str] = None,
        confirmed: bool = False
    ) -> ActionResult:
        """Execute semantic browser action with Human Confirmation Security Gate inside worker thread."""
        def _task():
            start = time.time()
            session = self.session_manager.get_session(user_id)
            if not session:
                session = UserBrowserSession(user_id=user_id)
                self.session_manager._sessions[user_id] = session

            # 1. Security & Human Confirmation Gate
            risk_level, requires_confirm, reason = security_manager.assess_action_risk(
                action=action, selector=selector, text_input=text_input, url=url
            )

            if requires_confirm and not confirmed:
                confirm_id = str(uuid.uuid4())
                expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + CONFIRMATION_EXPIRY_SECONDS))
                confirm_req = ConfirmationRequest(
                    id=confirm_id,
                    user_id=user_id,
                    session_id=session.session_id,
                    action=action,
                    target=selector or url or f"element [{element_id}]" or "browser",
                    params={"text_input": text_input, "url": url, "element_id": element_id},
                    reason=reason or "High-risk browser action requires explicit authorization",
                    risk_level=risk_level,
                    status="pending",
                    expires_at=expires_at
                )
                session.pending_confirmations[confirm_id] = confirm_req

                return ActionResult(
                    action=action,
                    status="confirmation_required",
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"⚠️ Human Confirmation Required: {reason}. Approve action to proceed.",
                    confirmation=confirm_req,
                    data={"confirmation_id": confirm_id, "reason": reason, "risk_level": risk_level}
                )

            # 2. Ensure Browser is running
            if not session or not session.is_connected or not session.context:
                ok, msg, session = self.session_manager.launch_managed_browser(user_id)
                if not ok or not session or not session.context:
                    return ActionResult(
                        action=action,
                        status="error",
                        duration_ms=int((time.time() - start) * 1000),
                        message="Browser not connected. Start Chrome or launch managed browser.",
                        error="BROWSER_NOT_CONNECTED"
                    )

            # 3. Retrieve target page
            page, err = session.tab_manager.get_page_by_id(session.context, tab_id)
            if err or not page:
                return ActionResult(
                    action=action,
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=err or "Page not available",
                    error=err
                )

            # 4. Dispatch Semantic Action
            act = action.lower()
            if act == "navigate" and url:
                return PageController.navigate(page, url)
            elif act == "click":
                return PageController.click(
                    page,
                    selector=selector,
                    text=text_input,
                    element_id=element_id,
                    role=role,
                    name=name,
                    coordinates=coordinates
                )
            elif act in ("type", "fill") and text_input is not None:
                return PageController.type_text(page, text=text_input, selector=selector, element_id=element_id)
            elif act == "press_key" and (key or text_input):
                return PageController.press_key(page, key=key or text_input or "Enter")
            elif act == "scroll":
                return PageController.scroll(page, direction=direction, pixels=pixels)
            elif act == "hover":
                return PageController.hover(page, selector=selector, element_id=element_id)
            elif act == "wait":
                return PageController.wait(page, seconds=float(pixels if pixels < 60 else 1.0))
            elif act == "screenshot":
                return PageController.take_screenshot(page)
            elif act == "go_back":
                return PageController.go_back(page)
            elif act == "go_forward":
                return PageController.go_forward(page)
            elif act == "recover_page":
                return PageController.recover_invalid_page(page, user_goal=text_input or "")
            elif act == "generic_search":
                return PageController.generic_search(page, query=text_input or "")
            elif act == "snapshot":
                return self.snapshot(user_id, tab_id)
            # ---- New actions ----
            elif act == "select_option" and text_input:
                return PageController.select_option(page, value=text_input, selector=selector, element_id=element_id)
            elif act == "double_click":
                return PageController.double_click(page, selector=selector, element_id=element_id, text=text_input)
            elif act == "evaluate_js" and text_input:
                return PageController.evaluate_js(page, js_code=text_input)
            elif act == "reload":
                return PageController.reload(page)
            elif act == "get_attribute" and key:
                return PageController.get_attribute(page, attribute=key, selector=selector, element_id=element_id)
            elif act == "drag_drop" and selector and url:
                # selector = source CSS selector, url param reused for target selector
                return PageController.drag_drop(page, source_selector=selector, target_selector=url)
            elif act == "upload_file" and text_input:
                return PageController.upload_file(page, file_path=text_input, selector=selector, element_id=element_id)
            elif act == "mouse_scroll":
                # pixels param reused as delta_y; direction param reused to carry x,y as "x,y" string
                delta_y = float(pixels) if direction.lower() != "up" else -float(pixels)
                # Parse optional coordinates from text_input e.g. "400,300"
                cx: Optional[float] = None
                cy: Optional[float] = None
                if text_input and "," in text_input:
                    try:
                        parts = text_input.split(",", 1)
                        cx, cy = float(parts[0].strip()), float(parts[1].strip())
                    except Exception:
                        pass
                delta_x_val = 0.0
                return PageController.mouse_scroll(page, x=cx, y=cy, delta_x=delta_x_val, delta_y=delta_y)
            else:
                return ActionResult(
                    action=action,
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Unknown or unsupported browser action: '{action}'",
                    error="UNSUPPORTED_ACTION"
                )

        try:
            return self.worker.run(_task)
        except Exception as e:
            return ActionResult(
                action=action,
                status="error",
                duration_ms=0,
                message=f"Action '{action}' failed: {str(e)}",
                error=str(e)
            )

    def resolve_confirmation(self, user_id: int, confirmation_id: str, approved: bool) -> ActionResult:
        """Resolve a pending confirmation and execute the action if approved."""
        session = self.session_manager.get_session(user_id)
        if not session or confirmation_id not in session.pending_confirmations:
            return ActionResult(
                action="confirm",
                status="error",
                duration_ms=0,
                message=f"Confirmation request '{confirmation_id}' not found or expired.",
                error="CONFIRMATION_NOT_FOUND"
            )

        confirm_req = session.pending_confirmations.pop(confirmation_id)
        if not approved:
            confirm_req.status = "rejected"
            return ActionResult(
                action=confirm_req.action,
                status="error",
                duration_ms=0,
                message="Action was rejected by user.",
                error="CONFIRMATION_REJECTED",
                confirmation=confirm_req
            )

        confirm_req.status = "approved"
        params = confirm_req.params or {}
        return self.execute_action(
            user_id=user_id,
            action=confirm_req.action,
            selector=confirm_req.target if confirm_req.target.startswith("#") or confirm_req.target.startswith(".") else None,
            text_input=params.get("text_input"),
            url=params.get("url"),
            element_id=params.get("element_id"),
            confirmed=True
        )

# Global unified browser service
browser_service = BrowserService()
