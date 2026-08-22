"""Unified Browser Service with Multi-User Isolation, Session Management, and Human Confirmation."""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, PageSnapshot, ActionResult,
    ConfirmationRequest, RiskLevel
)
from browser.connection_manager import BrowserConnectionManager
from browser.tab_manager import TabManager
from browser.page_controller import PageController
from browser.security_manager import security_manager

CONFIRMATION_EXPIRY_SECONDS = 300  # 5 minutes

class UserBrowserSession:
    """Encapsulates isolated connection and tab state for a single user."""
    def __init__(self, user_id: int, mode: BrowserMode = BrowserMode.EXISTING_CDP, cdp_url: str = "http://127.0.0.1:9222"):
        self.user_id = user_id
        self.session_id = str(uuid.uuid4())
        self.connection = BrowserConnectionManager(mode=mode, cdp_url=cdp_url)
        self.tab_manager = TabManager()
        self.last_accessed_at = time.time()
        self.pending_confirmations: Dict[str, ConfirmationRequest] = {}

class BrowserService:
    """Production-grade Browser Service handling multi-user isolation and lifecycle."""

    def __init__(self):
        self._user_sessions: Dict[int, UserBrowserSession] = {}

    def _get_or_create_session(
        self,
        user_id: int = 1,
        mode: BrowserMode = BrowserMode.EXISTING_CDP,
        cdp_url: str = "http://127.0.0.1:9222"
    ) -> UserBrowserSession:
        """Retrieve active user session or instantiate a new isolated session."""
        session = self._user_sessions.get(user_id)
        if not session:
            session = UserBrowserSession(user_id=user_id, mode=mode, cdp_url=cdp_url)
            self._user_sessions[user_id] = session
        session.last_accessed_at = time.time()
        return session

    def connect(
        self,
        user_id: int = 1,
        mode: BrowserMode = BrowserMode.EXISTING_CDP,
        cdp_url: str = "http://127.0.0.1:9222"
    ) -> Tuple[bool, str, BrowserStatus]:
        """Connect user session to existing browser over CDP or managed mode."""
        session = self._get_or_create_session(user_id, mode=mode, cdp_url=cdp_url)
        success, msg, context = session.connection.connect(mode=mode, cdp_url=cdp_url)
        if success:
            session.tab_manager.sync_tabs(context)
        return success, msg, self.get_status(user_id)

    def disconnect(self, user_id: int = 1) -> Tuple[bool, str]:
        """Cleanly disconnect user browser session."""
        session = self._user_sessions.get(user_id)
        if session:
            session.connection.disconnect()
            session.tab_manager.sync_tabs(None)
            return True, "Disconnected from browser successfully."
        return True, "No active browser session was connected."

    def get_status(self, user_id: int = 1) -> BrowserStatus:
        """Return connectivity, active tabs, and metadata for user."""
        session = self._user_sessions.get(user_id)
        if not session or not session.connection.get_context():
            return BrowserStatus(
                connected=False,
                mode=BrowserMode.EXISTING_CDP,
                endpoint="http://127.0.0.1:9222",
                browser_type="Chromium",
                tabs_count=0,
                active_tab=None,
                tabs=[],
                user_id=user_id
            )

        status = session.connection.get_status()
        status.tabs = session.tab_manager.list_tabs(session.connection.get_context())
        status.tabs_count = len(status.tabs)
        status.active_tab = next((t for t in status.tabs if t.active), status.tabs[0] if status.tabs else None)
        status.user_id = user_id
        status.session_id = session.session_id
        return status

    def list_tabs(self, user_id: int = 1) -> List[TabInfo]:
        """List open tabs in user's connected browser."""
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()
        return session.tab_manager.list_tabs(ctx)

    def get_active_tab(self, user_id: int = 1) -> Optional[TabInfo]:
        """Get currently focused / active tab for user."""
        tabs = self.list_tabs(user_id)
        return next((t for t in tabs if t.active), tabs[0] if tabs else None)

    def select_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str, Optional[TabInfo]]:
        """Switch active tab in user's browser."""
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()
        return session.tab_manager.select_tab(ctx, tab_id)

    def open_new_tab(self, user_id: int, url: str = "about:blank") -> Tuple[bool, str, Optional[TabInfo]]:
        """Open a new tab in user's browser."""
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()
        if not ctx:
            # Auto-connect if not connected
            self.connect(user_id)
            ctx = session.connection.get_context()
        return session.tab_manager.open_new_tab(ctx, url)

    def close_tab(self, user_id: int, tab_id: str) -> Tuple[bool, str]:
        """Close specific tab in user's browser."""
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()
        return session.tab_manager.close_tab(ctx, tab_id)

    def snapshot(self, user_id: int = 1, tab_id: Optional[str] = None) -> ActionResult:
        """Capture DOM accessibility tree and interactive elements of active or target tab."""
        start = time.time()
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()

        if not ctx:
            # Attempt auto-connect
            ok, msg, _ = self.connect(user_id)
            ctx = session.connection.get_context()
            if not ok or not ctx:
                return ActionResult(
                    action="snapshot",
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message="Browser not connected. Please connect to your browser via CDP (http://127.0.0.1:9222).",
                    error="BROWSER_NOT_CONNECTED"
                )

        page, err = session.tab_manager.get_page_by_id(ctx, tab_id)
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

    def execute_action(
        self,
        user_id: int,
        action: str,
        selector: Optional[str] = None,
        text_input: Optional[str] = None,
        url: Optional[str] = None,
        element_id: Optional[int] = None,
        key: Optional[str] = None,
        direction: str = "down",
        pixels: int = 500,
        tab_id: Optional[str] = None,
        confirmed: bool = False
    ) -> ActionResult:
        """
        Execute semantic browser action with Human Confirmation Security Gate.
        """
        start = time.time()
        session = self._get_or_create_session(user_id)
        ctx = session.connection.get_context()

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

        # 2. Verify connection
        if not ctx:
            ok, _, _ = self.connect(user_id)
            ctx = session.connection.get_context()
            if not ok or not ctx:
                return ActionResult(
                    action=action,
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message="Browser not connected. Please connect via CDP (http://127.0.0.1:9222).",
                    error="BROWSER_NOT_CONNECTED"
                )

        # 3. Retrieve target page
        page, err = session.tab_manager.get_page_by_id(ctx, tab_id)
        if err or not page:
            return ActionResult(
                action=action,
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=err or "Page not available",
                error=err
            )

        # 4. Dispatch Action
        act = action.lower()
        if act == "navigate" and url:
            return PageController.navigate(page, url)
        elif act == "click":
            return PageController.click(page, selector=selector, text=text_input, element_id=element_id)
        elif act in ("type", "fill") and text_input is not None:
            return PageController.type_text(page, text=text_input, selector=selector, element_id=element_id)
        elif act == "press_key" and (key or text_input):
            return PageController.press_key(page, key=key or text_input or "Enter")
        elif act == "scroll":
            return PageController.scroll(page, direction=direction, pixels=pixels)
        elif act == "screenshot":
            return PageController.take_screenshot(page)
        elif act == "go_back":
            return PageController.go_back(page)
        elif act == "go_forward":
            return PageController.go_forward(page)
        elif act == "snapshot":
            return self.snapshot(user_id, tab_id)
        else:
            return ActionResult(
                action=action,
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Unknown or unsupported browser action: '{action}'",
                error="UNSUPPORTED_ACTION"
            )

    def resolve_confirmation(self, user_id: int, confirmation_id: str, approved: bool) -> ActionResult:
        """Resolve a pending confirmation and execute the action if approved."""
        session = self._user_sessions.get(user_id)
        if not session or confirmation_id not in session.pending_confirmations:
            return ActionResult(
                action="resolve_confirmation",
                status="error",
                message="Confirmation request not found or expired.",
                error="CONFIRMATION_NOT_FOUND"
            )

        req = session.pending_confirmations.pop(confirmation_id)
        if not approved:
            req.status = "rejected"
            return ActionResult(
                action=req.action,
                status="error",
                message="Action cancelled by user approval denial.",
                error="CONFIRMATION_REJECTED"
            )

        req.status = "approved"
        # Execute confirmed action
        return self.execute_action(
            user_id=user_id,
            action=req.action,
            selector=req.target if req.target.startswith(("#", ".", "[")) else None,
            text_input=req.params.get("text_input"),
            url=req.params.get("url"),
            element_id=req.params.get("element_id"),
            confirmed=True
        )

# Global Browser Service singleton
browser_service = BrowserService()
