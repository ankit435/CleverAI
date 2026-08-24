"""Per-user Stagehand session lifecycle: connect (existing Chrome via CDP) or
launch (managed local Chromium), track tabs, and disconnect/close cleanly.

Everything here runs *inside* the coroutines submitted to `browser.async_worker`
(the single background event-loop thread) — never call these methods directly
from arbitrary threads without going through that worker.
"""
import os
from typing import Dict, Optional

from stagehand import Stagehand, local_browser

from browser.llm_bridge import nvidia_generate
from browser.schema import BrowserMode, BrowserStatus, ConfirmationRequest, TabInfo

DEFAULT_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222")


class UserBrowserSession:
    """Holds one user's live Stagehand + browser handle."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.stagehand: Optional[Stagehand] = None
        self.browser = None  # StagehandBrowser handle (local_browser.launch/connect result)
        self.mode: BrowserMode = BrowserMode.EXISTING_CDP
        self.cdp_endpoint: Optional[str] = None
        self.pending_confirmations: Dict[str, ConfirmationRequest] = {}

    @property
    def is_connected(self) -> bool:
        return self.stagehand is not None and self.stagehand.initialized

    async def connect_existing(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        """Attach to the user's already-running Chrome/Edge via CDP (preserves logins)."""
        await self.close()
        self.browser = await local_browser.connect(cdp_url=cdp_url)
        self.stagehand = await Stagehand.create(browser=self.browser, model=nvidia_generate)
        self.mode = BrowserMode.EXISTING_CDP
        self.cdp_endpoint = cdp_url

    async def launch_managed(self, headless: bool = False) -> None:
        """Launch a fresh, Stagehand-managed local Chromium instance."""
        await self.close()
        self.browser = await local_browser.launch(headless=headless)
        self.stagehand = await Stagehand.create(browser=self.browser, model=nvidia_generate)
        self.mode = BrowserMode.MANAGED_BROWSER
        self.cdp_endpoint = None

    async def close(self) -> None:
        """Best-effort teardown of the Stagehand client and underlying browser handle."""
        if self.stagehand is not None:
            try:
                await self.stagehand.close()
            except Exception:
                pass
            self.stagehand = None
        if self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

    async def list_tabs(self) -> list:
        if not self.is_connected:
            return []
        pages = await self.browser.context.pages()
        active = await self.browser.context.active_page()
        active_id = active.page_id if active else None
        tabs = []
        for page in pages:
            try:
                url = await page.url()
                title = await page.title()
            except Exception:
                url, title = "about:blank", "Untitled"
            tabs.append(TabInfo(id=page.page_id, title=title or "Untitled", url=url or "about:blank", active=(page.page_id == active_id)))
        return tabs

    async def get_status(self) -> BrowserStatus:
        if not self.is_connected:
            return BrowserStatus(connected=False, user_id=self.user_id, mode=self.mode)
        tabs = await self.list_tabs()
        active_tab = next((t for t in tabs if t.active), tabs[0] if tabs else None)
        return BrowserStatus(
            connected=True,
            mode=self.mode,
            cdp_endpoint=self.cdp_endpoint,
            tabs_count=len(tabs),
            active_tab=active_tab,
            tabs=tabs,
            user_id=self.user_id,
        )


class BrowserSessionManager:
    """Tracks one `UserBrowserSession` per authenticated user_id."""

    def __init__(self) -> None:
        self._sessions: Dict[int, UserBrowserSession] = {}

    def get_or_create(self, user_id: int) -> UserBrowserSession:
        session = self._sessions.get(user_id)
        if session is None:
            session = UserBrowserSession(user_id)
            self._sessions[user_id] = session
        return session

    def get(self, user_id: int) -> Optional[UserBrowserSession]:
        return self._sessions.get(user_id)


browser_session_manager = BrowserSessionManager()
