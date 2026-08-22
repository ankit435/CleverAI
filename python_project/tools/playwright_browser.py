"""Playwright Browser Bridge tool delegating to the unified BrowserService."""
from typing import Any, Dict, Optional
from langchain_core.tools import tool
from browser.service import browser_service

def perform_interactive_browser_action(
    url: str,
    action: str = "navigate",
    selector: Optional[str] = None,
    text_input: Optional[str] = None,
    user_id: int = 1
) -> Dict[str, Any]:
    """Execute browser action through the unified BrowserService."""
    res = browser_service.execute_action(
        user_id=user_id,
        action=action,
        selector=selector,
        text_input=text_input,
        url=url
    )
    status_data = browser_service.get_status(user_id=user_id)
    return {
        "title": res.current_title or (status_data.active_tab.title if status_data.active_tab else "Browser Page"),
        "url": res.current_url or (status_data.active_tab.url if status_data.active_tab else url),
        "action": res.message,
        "content": res.snapshot.formatted_snapshot if res.snapshot else res.message,
        "links": [{"text": t.title, "url": t.url} for t in status_data.tabs],
        "status": res.status,
        "execution_time_ms": res.duration_ms,
        "formatted": res.snapshot.formatted_snapshot if res.snapshot else res.message
    }

@tool
def interactive_browser_action(
    url: str,
    action: str = "navigate",
    selector: Optional[str] = None,
    text_input: Optional[str] = None
) -> str:
    """
    Connect to existing browser or spawn headless session to navigate URLs, click elements, type search queries, and read page snapshots.
    """
    res = perform_interactive_browser_action(url, action, selector, text_input)
    return res["formatted"]
