import os
import time
from typing import Dict, Optional

from stagehand import Stagehand, local_browser

from browser.errors import BrowserUnavailableError
from browser.llm_bridge import nvidia_generate
from browser.schema import BrowserMode, BrowserStatus, ConfirmationRequest, TabInfo

DEFAULT_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222")
DEFAULT_IDLE_TIMEOUT_SECONDS = float(os.getenv("BROWSER_IDLE_TIMEOUT_SECONDS", "300.0"))


class UserBrowserSession:
    """Holds one user's live Stagehand + browser handle."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.stagehand: Optional[Stagehand] = None
        self.browser = None  # StagehandBrowser handle (local_browser.launch/connect result)
        self.mode: BrowserMode = BrowserMode.EXISTING_CDP
        self.cdp_endpoint: Optional[str] = None
        self.pending_confirmations: Dict[str, ConfirmationRequest] = {}
        self.confirmation_threads: Dict[str, Optional[str]] = {}
        self.last_accessed_at: float = time.time()
        # Maps conversation thread_id -> Stagehand page_id, so each conversation
        # gets its own dedicated tab inside this ONE shared browser instance
        # instead of spawning a new browser (or fighting over one page) per turn.
        self.thread_tabs: Dict[str, str] = {}

    def touch(self) -> None:
        """Update last accessed timestamp on activity."""
        self.last_accessed_at = time.time()

    @property
    def is_connected(self) -> bool:
        return self.stagehand is not None and self.stagehand.initialized

    async def connect_existing(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        """Attach to the user's already-running Chrome/Edge via CDP (preserves logins)."""
        await self.close()
        try:
            self.browser = await local_browser.connect(cdp_url=cdp_url)
            self.stagehand = await Stagehand.create(browser=self.browser, model=nvidia_generate)
        except Exception as exc:
            # Connection refused / no CDP endpoint listening / Stagehand init failure —
            # this means the capability genuinely cannot be used right now, not that
            # a specific action failed. Callers must surface this as UNAVAILABLE.
            raise BrowserUnavailableError(
                f"Could not connect to an existing browser at {cdp_url}: {exc}"
            ) from exc
        self.mode = BrowserMode.EXISTING_CDP
        self.cdp_endpoint = cdp_url
        self.touch()

    async def launch_managed(self, headless: bool = False) -> None:
        """Launch a fresh, Stagehand-managed local Chromium instance."""
        await self.close()
        try:
            self.browser = await local_browser.launch(headless=headless)
            self.stagehand = await Stagehand.create(browser=self.browser, model=nvidia_generate)
        except Exception as exc:
            # Chromium binary missing, sandbox/permissions failure, Stagehand init
            # failure, etc. — the browser capability itself is unavailable, not a
            # single action within it.
            raise BrowserUnavailableError(f"Could not launch a managed local browser: {exc}") from exc
        self.mode = BrowserMode.MANAGED_BROWSER
        self.cdp_endpoint = None
        self.touch()

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
        self.thread_tabs.clear()

    async def list_tabs(self) -> list:
        if not self.is_connected:
            return []
        self.touch()
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

    async def get_page_for_thread(self, thread_id: Optional[str]):
        """
        Return the dedicated tab (page) for a given conversation, creating one on
        first use and switching it to active. If no thread_id is supplied, falls
        back to whatever tab is currently active (or creates one).

        Conversations never spawn a new browser — they only ever get their own
        TAB inside this one shared per-user browser instance. If the user
        manually closed that tab in their real browser, a fresh one is
        transparently recreated and re-bound to the same thread_id.
        """
        pages = await self.browser.context.pages()
        page_by_id = {p.page_id: p for p in pages}

        if thread_id:
            existing_page_id = self.thread_tabs.get(thread_id)
            if existing_page_id and existing_page_id in page_by_id:
                page = page_by_id[existing_page_id]
                await self.browser.context.set_active_page(page)
                self.touch()
                return page

        # No tab bound yet for this conversation (or it was closed) — reuse an
        # unbound existing tab if one exists, otherwise open a fresh one.
        bound_ids = set(self.thread_tabs.values())
        unbound_page = next((p for p in pages if p.page_id not in bound_ids), None)
        page = unbound_page or await self.browser.context.new_page()
        await self.browser.context.set_active_page(page)

        if thread_id:
            self.thread_tabs[thread_id] = page.page_id

        self.touch()
        return page

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

    def unbind_thread(self, thread_id: str) -> None:
        """Forget a conversation's dedicated tab mapping (does not close the tab)."""
        self.thread_tabs.pop(thread_id, None)


class BrowserSessionManager:
    """Tracks one `UserBrowserSession` per authenticated user_id."""

    def __init__(self) -> None:
        self._sessions: Dict[int, UserBrowserSession] = {}

    def get_or_create(self, user_id: int) -> UserBrowserSession:
        session = self._sessions.get(user_id)
        if session is None:
            session = UserBrowserSession(user_id)
            self._sessions[user_id] = session
        session.touch()
        return session

    def get(self, user_id: int) -> Optional[UserBrowserSession]:
        session = self._sessions.get(user_id)
        if session:
            session.touch()
        return session

    async def reap_idle_sessions(self, idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> int:
        """Reap and close any sessions that have been idle for longer than the idle timeout."""
        now = time.time()
        reaped_count = 0
        for session in list(self._sessions.values()):
            if session.is_connected and (now - session.last_accessed_at) > idle_timeout_seconds:
                await session.close()
                reaped_count += 1
        return reaped_count


browser_session_manager = BrowserSessionManager()
