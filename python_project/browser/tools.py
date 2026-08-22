"""Structured LangChain Tools for the Browser AI Agent."""
from typing import Optional
from langchain_core.tools import tool
from browser.service import browser_service

@tool
def browser_status() -> str:
    """Check browser connectivity, active tab, and open tabs count."""
    status = browser_service.get_status(user_id=1)
    if not status.connected:
        return (
            "Browser Status: Disconnected\n"
            "Mode: Existing CDP (http://127.0.0.1:9222)\n"
            "To connect, ensure Chrome or Edge is open with remote debugging enabled (--remote-debugging-port=9222)."
        )
    tabs_str = "\n".join(f"- [{t.id}] {t.title} ({t.url})" for t in status.tabs)
    return (
        f"Browser Status: Connected ({status.browser_type})\n"
        f"Active Tab: {status.active_tab.title if status.active_tab else 'None'} ({status.active_tab.url if status.active_tab else ''})\n"
        f"Total Tabs ({status.tabs_count}):\n{tabs_str}"
    )

@tool
def browser_list_tabs() -> str:
    """List all open tabs, titles, and URLs in the user's connected browser."""
    tabs = browser_service.list_tabs(user_id=1)
    if not tabs:
        return "No open tabs found or browser is not connected."
    return "\n".join(
        f"[{t.id}] {'[ACTIVE] ' if t.active else ''}{t.title} — {t.url}" for t in tabs
    )

@tool
def browser_get_active_tab() -> str:
    """Get the currently active/focused tab in the user's browser."""
    tab = browser_service.get_active_tab(user_id=1)
    if not tab:
        return "No active tab found. Use 'browser_list_tabs' or 'browser_select_tab'."
    return f"Active Tab: [{tab.id}] {tab.title}\nURL: {tab.url}"

@tool
def browser_select_tab(tab_id: str) -> str:
    """
    Switch the active focused tab in the browser by tab ID.
    Args:
        tab_id: Tab identifier (e.g. 'tab_1', 'tab_2').
    """
    success, msg, tab = browser_service.select_tab(user_id=1, tab_id=tab_id)
    if success and tab:
        return f"Switched to [{tab.id}] {tab.title} ({tab.url})"
    return f"Failed to switch tab: {msg}"

@tool
def browser_navigate(url: str, tab_id: Optional[str] = None) -> str:
    """
    Navigate the browser tab to a specified web URL.
    Args:
        url: The web URL to navigate to (e.g. 'https://github.com', 'https://news.ycombinator.com').
        tab_id: Optional tab ID to navigate. Defaults to active tab.
    """
    res = browser_service.execute_action(user_id=1, action="navigate", url=url, tab_id=tab_id)
    return res.message

@tool
def browser_snapshot(tab_id: Optional[str] = None) -> str:
    """
    Capture a structured accessibility snapshot of the page showing visible text and numbered interactive elements [1], [2].
    Args:
        tab_id: Optional tab ID to snapshot. Defaults to active tab.
    """
    res = browser_service.snapshot(user_id=1, tab_id=tab_id)
    if res.status == "success" and res.snapshot:
        return res.snapshot.formatted_snapshot
    return f"Snapshot error: {res.message}"

@tool
def browser_click(
    selector: Optional[str] = None,
    text: Optional[str] = None,
    element_id: Optional[int] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Click an interactive button, link, or element on the page using its numbered snapshot ID, text, or CSS selector.
    Args:
        selector: Optional CSS selector (e.g. 'button.submit', '#search-btn').
        text: Optional visible text of the button or link (e.g. 'Pull requests', 'Compose').
        element_id: Optional numbered ID from the latest snapshot (e.g. 1, 2, 3).
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=1, action="click", selector=selector, text_input=text, element_id=element_id, tab_id=tab_id
    )
    return res.message

@tool
def browser_type(
    text: str,
    selector: Optional[str] = None,
    element_id: Optional[int] = None,
    press_enter: bool = False,
    tab_id: Optional[str] = None
) -> str:
    """
    Type text into an input field, search box, or textarea.
    Args:
        text: The string text to type.
        selector: Optional CSS selector for the input field.
        element_id: Optional numbered ID from page snapshot (e.g. 1, 2).
        press_enter: If true, presses Enter after typing (submitting search).
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=1, action="type", text_input=text, selector=selector, element_id=element_id, tab_id=tab_id
    )
    if press_enter and res.status == "success":
        browser_service.execute_action(user_id=1, action="press_key", key="Enter", tab_id=tab_id)
        return f"{res.message} and pressed Enter."
    return res.message

@tool
def browser_press_key(key: str = "Enter", tab_id: Optional[str] = None) -> str:
    """
    Press a keyboard key on the active page (e.g. 'Enter', 'Escape', 'Tab', 'ArrowDown').
    Args:
        key: The key to press.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=1, action="press_key", key=key, tab_id=tab_id)
    return res.message

@tool
def browser_scroll(direction: str = "down", pixels: int = 500, tab_id: Optional[str] = None) -> str:
    """
    Scroll the active page up or down.
    Args:
        direction: Direction to scroll ('down', 'up', 'top', 'bottom').
        pixels: Number of pixels to scroll (default 500).
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=1, action="scroll", direction=direction, pixels=pixels, tab_id=tab_id
    )
    return res.message

@tool
def browser_screenshot(tab_id: Optional[str] = None) -> str:
    """
    Capture a screenshot of the active browser tab.
    Args:
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=1, action="screenshot", tab_id=tab_id)
    return res.message

@tool
def browser_go_back(tab_id: Optional[str] = None) -> str:
    """Navigate back in browser history."""
    res = browser_service.execute_action(user_id=1, action="go_back", tab_id=tab_id)
    return res.message

@tool
def browser_go_forward(tab_id: Optional[str] = None) -> str:
    """Navigate forward in browser history."""
    res = browser_service.execute_action(user_id=1, action="go_forward", tab_id=tab_id)
    return res.message

ALL_BROWSER_TOOLS = [
    browser_status,
    browser_list_tabs,
    browser_get_active_tab,
    browser_select_tab,
    browser_navigate,
    browser_snapshot,
    browser_click,
    browser_type,
    browser_press_key,
    browser_scroll,
    browser_screenshot,
    browser_go_back,
    browser_go_forward
]
