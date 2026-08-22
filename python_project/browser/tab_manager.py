"""Tab Manager: Enumerate, select, attach, track, and manage tabs across browser contexts."""
from typing import Dict, List, Optional, Tuple
from playwright.sync_api import BrowserContext, Page
from browser.schema import TabInfo

class TabManager:
    """Tracks and selects tabs from connected Playwright BrowserContext."""

    def __init__(self):
        self._active_tab_id: Optional[str] = None
        self._tab_map: Dict[str, Page] = {}

    def sync_tabs(self, context: Optional[BrowserContext]) -> List[TabInfo]:
        """Synchronize internal map with live pages in the BrowserContext."""
        if not context:
            self._tab_map.clear()
            self._active_tab_id = None
            return []

        live_pages = context.pages
        new_tab_map: Dict[str, Page] = {}
        tab_infos: List[TabInfo] = []

        for idx, page in enumerate(live_pages):
            tab_id = f"tab_{idx + 1}"
            new_tab_map[tab_id] = page

            try:
                title = page.title() or "Untitled"
                url = page.url or "about:blank"
            except Exception:
                title = "Tab"
                url = "about:blank"

            is_active = (self._active_tab_id == tab_id) if self._active_tab_id else (idx == 0)
            if is_active:
                self._active_tab_id = tab_id

            tab_infos.append(TabInfo(
                id=tab_id,
                title=title,
                url=url,
                active=is_active
            ))

        self._tab_map = new_tab_map
        if not self._active_tab_id and tab_infos:
            self._active_tab_id = tab_infos[0].id

        return tab_infos

    def list_tabs(self, context: Optional[BrowserContext]) -> List[TabInfo]:
        """Return list of all current tabs with active state."""
        return self.sync_tabs(context)

    def get_page_by_id(self, context: Optional[BrowserContext], tab_id: Optional[str] = None) -> Tuple[Optional[Page], Optional[str]]:
        """Retrieve target Playwright Page instance by tab_id or active tab."""
        self.sync_tabs(context)
        target_id = tab_id or self._active_tab_id

        if not target_id:
            if self._tab_map:
                target_id = next(iter(self._tab_map.keys()))
                self._active_tab_id = target_id
            else:
                return None, "No active tabs available."

        page = self._tab_map.get(target_id)
        if not page:
            return None, f"Tab '{target_id}' not found. Available tabs: {list(self._tab_map.keys())}"

        return page, None

    def select_tab(self, context: Optional[BrowserContext], tab_id: str) -> Tuple[bool, str, Optional[TabInfo]]:
        """Select a tab, focus it, and make it active."""
        self.sync_tabs(context)
        page = self._tab_map.get(tab_id)
        if not page:
            return False, f"Tab with ID '{tab_id}' does not exist.", None

        try:
            page.bring_to_front()
            self._active_tab_id = tab_id
            title = page.title() or "Untitled"
            url = page.url or "about:blank"
            return True, f"Selected and switched to tab '{tab_id}' ({title})", TabInfo(
                id=tab_id, title=title, url=url, active=True
            )
        except Exception as e:
            return False, f"Failed to focus tab '{tab_id}': {str(e)}", None

    def open_new_tab(self, context: Optional[BrowserContext], url: str = "about:blank") -> Tuple[bool, str, Optional[TabInfo]]:
        """Open a new tab in the current browser context and navigate to URL."""
        if not context:
            return False, "Browser context not connected.", None

        try:
            page = context.new_page()
            if url and url != "about:blank":
                page.goto(url, wait_until="domcontentloaded")

            tabs = self.sync_tabs(context)
            new_tab = tabs[-1] if tabs else None
            if new_tab:
                self._active_tab_id = new_tab.id
                return True, f"Opened new tab '{new_tab.id}' at '{url}'", new_tab
            return True, f"Opened new tab at '{url}'", None
        except Exception as e:
            return False, f"Failed to open new tab: {str(e)}", None

    def close_tab(self, context: Optional[BrowserContext], tab_id: str) -> Tuple[bool, str]:
        """Close a specific tab by ID."""
        page, err = self.get_page_by_id(context, tab_id)
        if err or not page:
            return False, err or "Tab not found"

        try:
            page.close()
            self.sync_tabs(context)
            return True, f"Closed tab '{tab_id}' successfully."
        except Exception as e:
            return False, f"Failed to close tab '{tab_id}': {str(e)}"
