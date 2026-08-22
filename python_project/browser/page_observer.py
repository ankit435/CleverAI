"""Page Observer Engine: Collects live DOM state, accessibility tree, and semantic snapshot."""
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page
from browser.schema import PageSnapshot, PageState
from browser.snapshot import snapshot_parser, JS_ACCESSIBILITY_EXTRACTOR
from browser.page_state_classifier import page_state_classifier

class PageObserver:
    """Collects multi-modal state from active Playwright page and produces structured PageSnapshot."""

    @staticmethod
    def observe(page: Page, active_tab_id: str = "tab_1", http_status: Optional[int] = None) -> PageSnapshot:
        """Capture complete DOM observation and produce token-optimized PageSnapshot with state classification."""
        title = page.title() or "Untitled"
        url = page.url or "about:blank"

        # 1. Execute JS accessibility extractor
        elements_data: List[Dict[str, Any]] = []
        try:
            elements_data = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
        except Exception:
            pass

        # 2. Extract visible body text
        visible_text = ""
        try:
            visible_text = page.inner_text("body") or ""
        except Exception:
            pass

        # 3. Classify Page State
        state = page_state_classifier.classify(page, visible_text=visible_text, http_status=http_status)

        # 4. Build Structured Snapshot
        snapshot = snapshot_parser.build_snapshot(
            title=title,
            url=url,
            active_tab_id=active_tab_id,
            elements_data=elements_data,
            visible_text=visible_text
        )
        snapshot.page_state = state

        return snapshot

page_observer = PageObserver()
