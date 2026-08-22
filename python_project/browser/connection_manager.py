"""Browser Connection Manager: Connect to existing CDP Chrome/Edge, Extension, or Managed instances."""
import os
import time
import httpx
from typing import Any, Dict, Optional, Tuple
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Playwright
from browser.schema import BrowserMode, BrowserStatus, TabInfo

DEFAULT_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222")

class BrowserConnectionManager:
    """Manages browser lifecycle, CDP connection to existing browsers, and multi-user isolation."""

    def __init__(self, mode: BrowserMode = BrowserMode.EXISTING_CDP, cdp_url: str = DEFAULT_CDP_URL):
        self.mode = mode
        self.cdp_url = cdp_url
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._is_connected = False
        self._last_connected_at: Optional[float] = None
        self._browser_info: Dict[str, Any] = {}

    def is_cdp_endpoint_alive(self, url: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Check if target CDP endpoint /json/version is reachable."""
        target_url = url or self.cdp_url
        version_url = f"{target_url.rstrip('/')}/json/version"
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(version_url)
                if res.status_code == 200:
                    info = res.json()
                    return True, None, info
                return False, f"CDP endpoint returned HTTP {res.status_code}", None
        except Exception as e:
            return False, f"CDP endpoint '{target_url}' is not reachable: {str(e)}", None

    def connect(
        self,
        mode: Optional[BrowserMode] = None,
        cdp_url: Optional[str] = None,
        user_data_dir: Optional[str] = None
    ) -> Tuple[bool, str, Optional[BrowserContext]]:
        """
        Connect to an existing browser (CDP) or launch a persistent managed browser instance.
        Preserves existing user logins, cookies, tabs, and session state.
        """
        target_mode = mode or self.mode
        target_cdp = cdp_url or self.cdp_url

        # Disconnect any stale connection first
        self.disconnect()

        try:
            self._playwright = sync_playwright().start()

            if target_mode == BrowserMode.EXISTING_CDP:
                # 1. Verify CDP endpoint availability
                is_alive, err_msg, info = self.is_cdp_endpoint_alive(target_cdp)
                if not is_alive:
                    self.disconnect()
                    return False, (
                        f"Cannot connect to existing browser via CDP ({target_cdp}). "
                        f"{err_msg}. Ensure Chrome/Edge was launched with '--remote-debugging-port=9222'."
                    ), None

                self._browser_info = info or {}
                # 2. Connect over CDP without creating a new browser
                self._browser = self._playwright.chromium.connect_over_cdp(target_cdp)
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                else:
                    self._context = self._browser.new_context()

                self._is_connected = True
                self._last_connected_at = time.time()
                return True, f"Successfully connected to existing browser over CDP ({target_cdp})", self._context

            elif target_mode == BrowserMode.MANAGED_BROWSER:
                # Launch a managed persistent context (preserving user storage if profile dir given)
                data_dir = user_data_dir or os.path.expanduser("~/.clever_browser_profile")
                os.makedirs(data_dir, exist_ok=True)
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=data_dir,
                    headless=False,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                self._is_connected = True
                self._last_connected_at = time.time()
                return True, f"Launched managed browser with persistent profile at '{data_dir}'", self._context

            elif target_mode == BrowserMode.REMOTE_BROWSER:
                self._browser = self._playwright.chromium.connect(target_cdp)
                self._context = self._browser.new_context()
                self._is_connected = True
                self._last_connected_at = time.time()
                return True, f"Connected to remote browser at '{target_cdp}'", self._context

            else:
                self.disconnect()
                return False, f"Unsupported browser connection mode: '{target_mode}'", None

        except Exception as err:
            self.disconnect()
            return False, f"Browser connection error: {str(err)}", None

    def get_context(self) -> Optional[BrowserContext]:
        """Return the active BrowserContext if connected."""
        if self._is_connected and self._context:
            return self._context
        return None

    def disconnect(self) -> None:
        """Cleanly disconnect from browser without killing the user's running browser."""
        try:
            if self._context and self.mode != BrowserMode.EXISTING_CDP:
                self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

        self._playwright = None
        self._browser = None
        self._context = None
        self._is_connected = False
        self._browser_info = {}

    def get_status(self) -> BrowserStatus:
        """Return structured connectivity and browser status."""
        pages_count = len(self._context.pages) if (self._context and self._is_connected) else 0
        active_tab: Optional[TabInfo] = None
        tabs: list[TabInfo] = []

        if self._context and self._is_connected:
            for idx, p in enumerate(self._context.pages):
                try:
                    title = p.title() or "Untitled"
                    url = p.url or "about:blank"
                    is_active = (idx == 0)  # Default first page as active if not designated
                    tab_item = TabInfo(id=f"tab_{idx+1}", title=title, url=url, active=is_active)
                    tabs.append(tab_item)
                    if is_active:
                        active_tab = tab_item
                except Exception:
                    continue

        return BrowserStatus(
            connected=self._is_connected,
            mode=self.mode,
            endpoint=self.cdp_url,
            browser_type=self._browser_info.get("Browser", "Chromium"),
            version=self._browser_info.get("Protocol-Version"),
            tabs_count=pages_count,
            active_tab=active_tab,
            tabs=tabs
        )
