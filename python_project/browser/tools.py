"""Structured LangChain Tools for the Browser AI Agent."""
from typing import Optional
from langchain_core.tools import tool
from browser.service import browser_service

@tool
def browser_status() -> str:
    """Check browser connectivity, active tab, and open tabs count."""
    status = browser_service.get_status(user_id=1)
    if not status.connected:
        browser_service.connect(user_id=1)
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

def _clean_tab_id(tab_id: Optional[str]) -> Optional[str]:
    if isinstance(tab_id, str) and tab_id.lower().strip() in ("none", "null", "undefined", "", "0"):
        return None
    return tab_id

@tool
def browser_select_tab(tab_id: str) -> str:
    """
    Switch the active focused tab in the browser by tab ID.
    Args:
        tab_id: Tab identifier (e.g. 'tab_1', 'tab_2').
    """
    cleaned = _clean_tab_id(tab_id) or "tab_1"
    success, msg, tab = browser_service.select_tab(user_id=1, tab_id=cleaned)
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
    cleaned = _clean_tab_id(tab_id)
    res = browser_service.execute_action(user_id=1, action="navigate", url=url, tab_id=cleaned)
    return res.message

@tool
def browser_snapshot(tab_id: Optional[str] = None) -> str:
    """
    Capture a structured accessibility snapshot of the page showing visible text and numbered interactive elements [1], [2].
    Args:
        tab_id: Optional tab ID to snapshot. Defaults to active tab.
    """
    cleaned = _clean_tab_id(tab_id)
    res = browser_service.snapshot(user_id=1, tab_id=cleaned)
    if res.status == "success" and res.snapshot:
        return res.snapshot.formatted_snapshot
    return f"Snapshot error: {res.message}"

@tool
def browser_click(
    selector: Optional[str] = None,
    text: Optional[str] = None,
    element_id: Optional[str] = None,
    role: Optional[str] = None,
    name: Optional[str] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Click an interactive button, link, or element using the multi-strategy resolution order:
    1. Accessibility role & accessible name (e.g. role='button', name='Submit')
    2. Stable DOM attributes (e.g. selector='[data-testid="search-btn"]')
    3. Visible text (e.g. text='Pull requests')
    4. Snapshot Element ID reference (e.g. element_id='e1' or '1')
    5. Visual location / coordinates
    Args:
        selector: Optional CSS / stable selector (e.g. 'button.submit', '[data-testid="btn"]').
        text: Optional visible text of the button or link (e.g. 'Repositories', 'Apply Now').
        element_id: Optional snapshot element identifier (e.g. 'e1', 'e15', or '15').
        role: Optional ARIA role (e.g. 'button', 'link', 'tab').
        name: Optional accessible name / label.
        tab_id: Optional target tab ID.
    """
    cleaned_tab = _clean_tab_id(tab_id)
    res = browser_service.execute_action(
        user_id=1,
        action="click",
        selector=selector,
        text_input=text,
        element_id=element_id,
        role=role,
        name=name,
        tab_id=cleaned_tab
    )
    return res.message

@tool
def browser_paginate(tab_id: Optional[str] = None) -> str:
    """
    Autonomously detect and click the 'Next' page, 'Load More', or pagination button on the active page.
    Args:
        tab_id: Optional target tab ID.
    """
    from browser.goal_tracker import goal_tracker
    cleaned_tab = _clean_tab_id(tab_id)
    
    def _task():
        session = browser_service.session_manager.get_session(1)
        if not session or not session.context:
            return "Browser not connected."
        page, err = session.tab_manager.get_page_by_id(session.context, cleaned_tab)
        if err or not page:
            return f"Page error: {err}"
        
        has_next, next_sel, next_id = goal_tracker.detect_pagination_or_next(page)
        if not has_next:
            return "No next page or pagination controls detected on current page."
        
        click_res = browser_service.execute_action(
            user_id=1, action="click", selector=next_sel, element_id=next_id, tab_id=cleaned_tab
        )
        return f"Paginated to next page: {click_res.message}"

    try:
        return browser_service.worker.run(_task)
    except Exception as e:
        return f"Pagination error: {str(e)}"

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
    res = browser_service.execute_action(user_id=1, action="go_back", tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_go_forward(tab_id: Optional[str] = None) -> str:
    """Navigate forward in browser history."""
    res = browser_service.execute_action(user_id=1, action="go_forward", tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_hover(selector: Optional[str] = None, element_id: Optional[str] = None, tab_id: Optional[str] = None) -> str:
    """Hover over an interactive button, menu, or element."""
    res = browser_service.execute_action(user_id=1, action="hover", selector=selector, element_id=element_id, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_wait(seconds: float = 1.0, tab_id: Optional[str] = None) -> str:
    """Wait dynamically for the active page to finish network / DOM settling."""
    res = browser_service.execute_action(user_id=1, action="wait", pixels=int(seconds), tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_generic_search(query: str, tab_id: Optional[str] = None) -> str:
    """
    Autonomously locate the search input box on the active webpage, type the query, and submit.
    Args:
        query: Search keywords or product query.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=1, action="generic_search", text_input=query, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_recover_page(user_goal: str = "", tab_id: Optional[str] = None) -> str:
    """
    Recover from a 404 or dead page by finding the Home/Navigation link and returning to a usable page.
    Args:
        user_goal: The user's original objective.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=1, action="recover_page", text_input=user_goal, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def navigate_browser(url: str) -> str:
    """Navigate the browser tab to a specified web URL."""
    res = browser_service.execute_action(user_id=1, action="navigate", url=url.strip())
    return res.message

@tool
def extract_text(selector: Optional[str] = None) -> str:
    """Extract visible text and structure from the active webpage or from a specific selector."""
    if selector and selector.strip():
        def _task():
            session = browser_service.session_manager.get_session(1)
            if not session or not session.context:
                return "Browser not connected."
            page, err = session.tab_manager.get_page_by_id(session.context, None)
            if err or not page:
                return f"Page error: {err}"
            try:
                locator = page.locator(selector)
                if locator.count() == 0:
                    return f"No elements found matching selector '{selector}'."
                texts = [locator.nth(i).inner_text().strip() for i in range(min(locator.count(), 10))]
                return "\n---\n".join(texts)
            except Exception as e:
                return f"Extraction error: {str(e)}"
        try:
            return browser_service.worker.run(_task)
        except Exception as ex:
            return f"Worker error: {str(ex)}"
    
    res = browser_service.snapshot(user_id=1)
    if res.status == "success" and res.snapshot:
        return res.snapshot.formatted_snapshot
    return f"Extraction error: {res.message}"

@tool
def get_elements(selector: Optional[str] = None) -> str:
    """Inspect interactive DOM elements on the page (links, buttons, inputs, accessibility tags)."""
    res = browser_service.snapshot(user_id=1)
    if res.status == "success" and res.snapshot:
        return res.snapshot.formatted_snapshot
    return f"Element inspection error: {res.message}"

@tool
def click_element(
    selector: Optional[str] = None,
    text: Optional[str] = None,
    element_id: Optional[str] = None
) -> str:
    """Click an interactive button, link, or element by selector, text, or snapshot ID."""
    res = browser_service.execute_action(
        user_id=1,
        action="click",
        selector=selector,
        text_input=text,
        element_id=element_id
    )
    return res.message

@tool
def type_text(
    text: str,
    selector: Optional[str] = None,
    element_id: Optional[int] = None,
    press_enter: bool = False
) -> str:
    """Type text into an input field, search box, or form field."""
    res = browser_service.execute_action(
        user_id=1,
        action="type",
        text_input=text,
        selector=selector,
        element_id=element_id
    )
    if press_enter and res.status == "success":
        browser_service.execute_action(user_id=1, action="press_key", key="Enter")
        return f"{res.message} and pressed Enter."
    return res.message

@tool
def press_key(key: str = "Enter") -> str:
    """Press a keyboard key on the active page (e.g. 'Enter', 'Escape', 'Tab', 'ArrowDown')."""
    res = browser_service.execute_action(user_id=1, action="press_key", key=key)
    return res.message

@tool
def wait_for_selector(selector: str, timeout_seconds: float = 5.0) -> str:
    """Wait for dynamic content, SPAs, or specific elements to appear on the page before acting."""
    def _task():
        session = browser_service.session_manager.get_session(1)
        if not session or not session.context:
            return "Browser not connected."
        page, err = session.tab_manager.get_page_by_id(session.context, None)
        if err or not page:
            return f"Page error: {err}"
        try:
            page.wait_for_selector(selector, timeout=int(timeout_seconds * 1000), state="visible")
            return f"Element '{selector}' is visible on page."
        except Exception as e:
            return f"Timeout waiting for '{selector}': {str(e)}"

    try:
        return browser_service.worker.run(_task)
    except Exception as ex:
        return f"Wait error: {str(ex)}"

@tool
def extract_hyperlinks() -> str:
    """Discover and extract all navigable hyperlinks on the active page with their labels."""
    def _task():
        session = browser_service.session_manager.get_session(1)
        if not session or not session.context:
            return "Browser not connected."
        page, err = session.tab_manager.get_page_by_id(session.context, None)
        if err or not page:
            return f"Page error: {err}"
        try:
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .filter(a => a.innerText && a.innerText.trim().length > 2)
                    .slice(0, 30)
                    .map(a => ({ text: a.innerText.trim(), href: a.href }));
            }""")
            if not links:
                return "No visible hyperlinks detected on page."
            return "\n".join(f"- [{l['text']}]({l['href']})" for l in links)
        except Exception as e:
            return f"Link extraction error: {str(e)}"

    try:
        return browser_service.worker.run(_task)
    except Exception as ex:
        return f"Worker error: {str(ex)}"

@tool
def screenshot() -> str:
    """Capture a visual screenshot of the current page for grounding."""
    res = browser_service.execute_action(user_id=1, action="screenshot")
    return res.message

@tool
def finish_task(result: str) -> str:
    """
    TERMINAL TOOL: Call this tool ONLY when you have satisfied the user's goal and collected the final verified data.
    Pass the complete, user-facing Markdown/JSON response to result.
    This will terminate the agent loop and return your final result directly to the user.
    Args:
        result: The complete, final user-facing Markdown answer with verified tables and direct links.
    """
    return f"[TASK_COMPLETED]: {result}"

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
    browser_hover,
    browser_wait,
    browser_screenshot,
    browser_go_back,
    browser_go_forward,
    browser_generic_search,
    browser_recover_page,
    browser_paginate,
    navigate_browser,
    extract_text,
    get_elements,
    click_element,
    type_text,
    press_key,
    wait_for_selector,
    extract_hyperlinks,
    screenshot,
    finish_task
]
