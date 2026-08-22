"""Browser Session Manager: Multi-mode discovery, lifecycle management, and user isolation."""
import os
import time
import httpx
from typing import Dict, Optional, Tuple, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Playwright
from browser.schema import BrowserMode, BrowserStatus, PolicyStrategy, PolicyDecision
from browser.tab_manager import TabManager
from browser.playwright_worker import playwright_worker

DEFAULT_CDP_URL = os.environ.get("BROWSER_CDP_URL", "http://127.0.0.1:9222")
IDLE_TIMEOUT_SECONDS = int(os.environ.get("BROWSER_IDLE_TIMEOUT", "1800"))  # 30 mins
DEFAULT_HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"

class UserBrowserSession:
    """Represents an isolated browser session belonging to a specific user."""

    def __init__(
        self,
        user_id: int,
        mode: BrowserMode = BrowserMode.EXISTING_CDP,
        cdp_url: str = DEFAULT_CDP_URL
    ):
        self.user_id = user_id
        self.mode = mode
        self.cdp_url = cdp_url
        self.session_id = f"sess_user_{user_id}_{int(time.time()*1000)}"
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.tab_manager = TabManager()
        self.is_connected = False
        self.is_managed = False
        self.created_at = time.time()
        self.last_accessed_at = time.time()
        self.browser_info: Dict[str, Any] = {}
        self.pending_confirmations: Dict[str, Any] = {}

    def touch(self):
        """Update last accessed timestamp to prevent idle reaping."""
        self.last_accessed_at = time.time()

    def disconnect(self):
        """Cleanly disconnect or close managed context without killing user's manual browser."""
        def _close_internal():
            try:
                if self.context and (self.is_managed or self.mode != BrowserMode.EXISTING_CDP):
                    self.context.close()
            except Exception:
                pass

            try:
                if self.browser:
                    self.browser.close()
            except Exception:
                pass

            try:
                if self.playwright:
                    self.playwright.stop()
            except Exception:
                pass

            self.playwright = None
            self.browser = None
            self.context = None
            self.is_connected = False
            self.is_managed = False
            self.tab_manager.sync_tabs(None)

        try:
            playwright_worker.run(_close_internal)
        except Exception:
            _close_internal()

class BrowserSessionManager:
    """Manages browser lifecycle, connection prioritization, auto-launching, and user isolation."""

    def __init__(self):
        self._sessions: Dict[int, UserBrowserSession] = {}

    def get_session(self, user_id: int) -> Optional[UserBrowserSession]:
        """Retrieve existing user session if active."""
        session = self._sessions.get(user_id)
        if session:
            session.touch()
        return session

    def detect_existing_browser(self, cdp_url: str = DEFAULT_CDP_URL) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Check if target CDP endpoint (e.g. http://127.0.0.1:9222) is reachable."""
        version_url = f"{cdp_url.rstrip('/')}/json/version"
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(version_url)
                if res.status_code == 200:
                    return True, res.json(), None
                return False, None, f"CDP returned HTTP {res.status_code}"
        except Exception as e:
            return False, None, f"CDP not reachable: {str(e)}"

    def connect_existing_browser(
        self,
        user_id: int,
        cdp_url: str = DEFAULT_CDP_URL
    ) -> Tuple[bool, str, Optional[UserBrowserSession]]:
        """Connect to user's running Chrome/Edge via CDP inside dedicated worker thread."""
        def _task():
            session = self._sessions.get(user_id)
            if not session:
                session = UserBrowserSession(user_id=user_id, mode=BrowserMode.EXISTING_CDP, cdp_url=cdp_url)
                self._sessions[user_id] = session
            else:
                session.disconnect()

            is_alive, info, err = self.detect_existing_browser(cdp_url)
            if not is_alive:
                return False, f"Existing browser not found on {cdp_url}. ({err})", None

            try:
                session.playwright = sync_playwright().start()
                session.browser = session.playwright.chromium.connect_over_cdp(cdp_url)
                contexts = session.browser.contexts
                session.context = contexts[0] if contexts else session.browser.new_context()
                session.mode = BrowserMode.EXISTING_CDP
                session.is_connected = True
                session.is_managed = False
                session.browser_info = info or {}
                session.tab_manager.sync_tabs(session.context)
                session.touch()
                return True, f"Connected to existing browser at {cdp_url}", session
            except Exception as e:
                session.disconnect()
                return False, f"Failed to connect via CDP: {str(e)}", None

        try:
            return playwright_worker.run(_task)
        except Exception as ex:
            return False, f"Worker connection error: {str(ex)}", None

    def launch_managed_browser(
        self,
        user_id: int,
        headless: bool = DEFAULT_HEADLESS
    ) -> Tuple[bool, str, Optional[UserBrowserSession]]:
        """
        Autonomously launch an isolated managed Chromium browser inside dedicated worker thread.
        """
        def _task():
            session = self._sessions.get(user_id)
            if not session:
                session = UserBrowserSession(user_id=user_id, mode=BrowserMode.MANAGED_BROWSER)
                self._sessions[user_id] = session
            elif session.is_connected and session.context:
                session.touch()
                return True, "Reusing existing active managed browser", session
            else:
                session.disconnect()

            try:
                profile_dir = os.path.expanduser(f"~/.clever_browser_profiles/user_{user_id}")
                os.makedirs(profile_dir, exist_ok=True)

                launch_flags = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--disable-features=OptimizationGuideModelDownloading,OptimizationHintsUI,NtpDriveModule"
                ]

                session.playwright = sync_playwright().start()
                try:
                    session.context = session.playwright.chromium.launch_persistent_context(
                        user_data_dir=profile_dir,
                        headless=headless,
                        args=launch_flags
                    )
                except Exception:
                    session.browser = session.playwright.chromium.launch(
                        headless=headless,
                        args=launch_flags
                    )
                    session.context = session.browser.new_context()

                if not session.context.pages:
                    p = session.context.new_page()
                    p.goto("about:blank", wait_until="domcontentloaded")

                session.mode = BrowserMode.MANAGED_BROWSER
                session.is_connected = True
                session.is_managed = True
                session.browser_info = {"Browser": "Managed Chromium", "Protocol-Version": "1.3"}
                session.tab_manager.sync_tabs(session.context)
                session.touch()
                return True, f"Launched managed browser with persistent profile for user {user_id}", session
            except Exception as e:
                session.disconnect()
                return False, f"Failed to launch managed browser: {str(e)}", None

        try:
            return playwright_worker.run(_task)
        except Exception as ex:
            return False, f"Worker launch error: {str(ex)}", None

    def ensure_browser_for_policy(
        self,
        user_id: int,
        policy: PolicyDecision
    ) -> Tuple[bool, str, Optional[UserBrowserSession]]:
        """
        Ensures a browser is ready based on the evaluated policy strategy.
        """
        session = self.get_session(user_id)
        if session and session.is_connected and session.context:
            return True, "Active session ready", session

        if policy.strategy == PolicyStrategy.USE_EXISTING:
            return self.connect_existing_browser(user_id)
        elif policy.strategy == PolicyStrategy.LAUNCH_MANAGED:
            is_cdp, _, _ = self.detect_existing_browser()
            if is_cdp:
                ok, msg, sess = self.connect_existing_browser(user_id)
                if ok:
                    return ok, msg, sess
            return self.launch_managed_browser(user_id)
        else:
            return False, "No browser required or user prompt needed", None

    def get_status(self, user_id: int) -> BrowserStatus:
        """Get live status and tab list for a specific user session."""
        def _task():
            session = self._sessions.get(user_id)
            if not session or not session.is_connected or not session.context:
                is_alive, info, _ = self.detect_existing_browser()
                return BrowserStatus(
                    connected=False,
                    mode=BrowserMode.EXISTING_CDP,
                    browser_type=info.get("Browser", "Chromium") if info else "Chromium",
                    cdp_endpoint=DEFAULT_CDP_URL,
                    active_tab=None,
                    tabs_count=0,
                    tabs=[]
                )

            tabs = session.tab_manager.sync_tabs(session.context)
            active_tab = next((t for t in tabs if t.active), tabs[0] if tabs else None)

            return BrowserStatus(
                connected=session.is_connected,
                mode=session.mode,
                browser_type=session.browser_info.get("Browser", "Chromium"),
                cdp_endpoint=session.cdp_url if session.mode == BrowserMode.EXISTING_CDP else None,
                active_tab=active_tab,
                tabs_count=len(tabs),
                tabs=tabs
            )

        try:
            return playwright_worker.run(_task)
        except Exception:
            return BrowserStatus(
                connected=False,
                mode=BrowserMode.EXISTING_CDP,
                browser_type="Chromium",
                cdp_endpoint=DEFAULT_CDP_URL,
                active_tab=None,
                tabs_count=0,
                tabs=[]
            )

    def reap_idle_sessions(self) -> int:
        """Close browser sessions that have been idle past IDLE_TIMEOUT_SECONDS."""
        now = time.time()
        reaped_count = 0
        for user_id, session in list(self._sessions.items()):
            if session.is_connected and (now - session.last_accessed_at) > IDLE_TIMEOUT_SECONDS:
                session.disconnect()
                reaped_count += 1
        return reaped_count

# Global singleton session manager
browser_session_manager = BrowserSessionManager()
