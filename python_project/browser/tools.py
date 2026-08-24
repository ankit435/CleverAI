"""Structured LangChain Tools for the Browser AI Agent."""
from typing import Optional
from langchain_core.tools import tool
from browser.service import browser_service
from browser.context import get_current_user_id

@tool
def browser_status() -> str:
    """Check browser connectivity, active tab, and open tabs count."""
    from browser.schema import BrowserMode
    status = browser_service.get_status(user_id=get_current_user_id())
    if not status.connected:
        # Prefer launching a managed Playwright Chromium rather than requiring the
        # user to start Chrome manually with --remote-debugging-port=9222.
        ok, _msg, _ = browser_service.session_manager.launch_managed_browser(user_id=get_current_user_id())
        if not ok:
            # Fall back to CDP connection if managed launch fails.
            browser_service.connect(user_id=get_current_user_id(), mode=BrowserMode.MANAGED_BROWSER)
        status = browser_service.get_status(user_id=get_current_user_id())

    if not status.connected:
        return (
            "Browser Status: Disconnected\n"
            "Attempted to launch a managed Chromium browser but it could not start.\n"
            "Alternatively, open Chrome with: google-chrome --remote-debugging-port=9222"
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
    status = browser_service.get_status(user_id=get_current_user_id())
    if not status.connected:
        browser_service.session_manager.launch_managed_browser(user_id=get_current_user_id())
    tabs = browser_service.list_tabs(user_id=get_current_user_id())
    if not tabs:
        return "No open tabs found. Browser may still be starting up — try again in a moment."
    return "\n".join(
        f"[{t.id}] {'[ACTIVE] ' if t.active else ''}{t.title} — {t.url}" for t in tabs
    )

@tool
def browser_get_active_tab() -> str:
    """Get the currently active/focused tab in the user's browser."""
    status = browser_service.get_status(user_id=get_current_user_id())
    if not status.connected:
        browser_service.session_manager.launch_managed_browser(user_id=get_current_user_id())
    tab = browser_service.get_active_tab(user_id=get_current_user_id())
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
    success, msg, tab = browser_service.select_tab(user_id=get_current_user_id(), tab_id=cleaned)
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
    res = browser_service.execute_action(user_id=get_current_user_id(), action="navigate", url=url, tab_id=cleaned)
    return res.message

@tool
def browser_snapshot(tab_id: Optional[str] = None) -> str:
    """
    Capture a structured accessibility snapshot of the page showing visible text and numbered interactive elements [1], [2].
    Args:
        tab_id: Optional tab ID to snapshot. Defaults to active tab.
    """
    cleaned = _clean_tab_id(tab_id)
    res = browser_service.snapshot(user_id=get_current_user_id(), tab_id=cleaned)
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
        user_id=get_current_user_id(),
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
        session = browser_service.session_manager.get_session(get_current_user_id())
        if not session or not session.context:
            return "Browser not connected."
        page, err = session.tab_manager.get_page_by_id(session.context, cleaned_tab)
        if err or not page:
            return f"Page error: {err}"
        
        has_next, next_sel, next_id = goal_tracker.detect_pagination_or_next(page)
        if not has_next:
            return "No next page or pagination controls detected on current page."
        
        click_res = browser_service.execute_action(
            user_id=get_current_user_id(), action="click", selector=next_sel, element_id=next_id, tab_id=cleaned_tab
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
        user_id=get_current_user_id(), action="type", text_input=text, selector=selector, element_id=element_id, tab_id=tab_id
    )
    if press_enter and res.status == "success":
        browser_service.execute_action(user_id=get_current_user_id(), action="press_key", key="Enter", tab_id=tab_id)
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
    res = browser_service.execute_action(user_id=get_current_user_id(), action="press_key", key=key, tab_id=tab_id)
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
        user_id=get_current_user_id(), action="scroll", direction=direction, pixels=pixels, tab_id=tab_id
    )
    return res.message

@tool
def browser_screenshot(tab_id: Optional[str] = None) -> str:
    """
    Capture a screenshot of the active browser tab.
    Args:
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=get_current_user_id(), action="screenshot", tab_id=tab_id)
    return res.message

@tool
def browser_go_back(tab_id: Optional[str] = None) -> str:
    """Navigate back in browser history."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="go_back", tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_go_forward(tab_id: Optional[str] = None) -> str:
    """Navigate forward in browser history."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="go_forward", tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_hover(selector: Optional[str] = None, element_id: Optional[str] = None, tab_id: Optional[str] = None) -> str:
    """Hover over an interactive button, menu, or element."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="hover", selector=selector, element_id=element_id, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_wait(seconds: float = 1.0, tab_id: Optional[str] = None) -> str:
    """Wait dynamically for the active page to finish network / DOM settling."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="wait", pixels=int(seconds), tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_generic_search(query: str, tab_id: Optional[str] = None) -> str:
    """
    Autonomously locate the search input box on the active webpage, type the query, and submit.
    Args:
        query: Search keywords or product query.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=get_current_user_id(), action="generic_search", text_input=query, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def browser_recover_page(user_goal: str = "", tab_id: Optional[str] = None) -> str:
    """
    Recover from a 404 or dead page by finding the Home/Navigation link and returning to a usable page.
    Args:
        user_goal: The user's original objective.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(user_id=get_current_user_id(), action="recover_page", text_input=user_goal, tab_id=_clean_tab_id(tab_id))
    return res.message

@tool
def navigate_browser(url: str) -> str:
    """Navigate the browser tab to a specified web URL."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="navigate", url=url.strip())
    return res.message

@tool
def extract_text(selector: Optional[str] = None) -> str:
    """Extract visible text and structure from the active webpage or from a specific selector."""
    if selector and selector.strip():
        def _task():
            session = browser_service.session_manager.get_session(get_current_user_id())
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
    
    res = browser_service.snapshot(user_id=get_current_user_id())
    if res.status == "success" and res.snapshot:
        return res.snapshot.formatted_snapshot
    return f"Extraction error: {res.message}"

@tool
def get_elements(selector: Optional[str] = None) -> str:
    """Inspect interactive DOM elements on the page (links, buttons, inputs, accessibility tags)."""
    res = browser_service.snapshot(user_id=get_current_user_id())
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
        user_id=get_current_user_id(),
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
        user_id=get_current_user_id(),
        action="type",
        text_input=text,
        selector=selector,
        element_id=element_id
    )
    if press_enter and res.status == "success":
        browser_service.execute_action(user_id=get_current_user_id(), action="press_key", key="Enter")
        return f"{res.message} and pressed Enter."
    return res.message

@tool
def press_key(key: str = "Enter") -> str:
    """Press a keyboard key on the active page (e.g. 'Enter', 'Escape', 'Tab', 'ArrowDown')."""
    res = browser_service.execute_action(user_id=get_current_user_id(), action="press_key", key=key)
    return res.message

@tool
def wait_for_selector(selector: str, timeout_seconds: float = 5.0) -> str:
    """Wait for dynamic content, SPAs, or specific elements to appear on the page before acting."""
    def _task():
        session = browser_service.session_manager.get_session(get_current_user_id())
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
        session = browser_service.session_manager.get_session(get_current_user_id())
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
    res = browser_service.execute_action(user_id=get_current_user_id(), action="screenshot")
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

# ============================================================
# New tools for full-coverage website interaction
# ============================================================

@tool
def browser_select_option(
    option: str,
    selector: Optional[str] = None,
    element_id: Optional[str] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Select an option from a <select> dropdown element by value or visible label.
    Use this for country pickers, size selectors, filter dropdowns, sort-by menus, etc.
    Args:
        option: The option value or label text to select (e.g. 'India', 'XL', 'Newest first').
        selector: CSS selector for the <select> element (e.g. 'select[name="country"]').
        element_id: Snapshot element ID from browser_snapshot (e.g. 'e5', '5').
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="select_option",
        text_input=option,
        selector=selector,
        element_id=element_id,
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_double_click(
    selector: Optional[str] = None,
    text: Optional[str] = None,
    element_id: Optional[str] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Double-click an element. Required for text selection, opening inline editors, file rename, and some rich-text apps.
    Args:
        selector: CSS selector of the element.
        text: Visible text of the element.
        element_id: Snapshot element ID.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="double_click",
        selector=selector,
        text_input=text,
        element_id=element_id,
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_evaluate_js(js_code: str) -> str:
    """
    Execute arbitrary JavaScript on the active page and return the result.
    Use as a last-resort escape hatch when standard tools cannot interact with a custom widget.
    Examples: read hidden state, trigger custom events, scroll to coordinates, call page APIs.
    Args:
        js_code: A JavaScript expression or statement (e.g. 'document.title', 'window.scrollY',
                 'document.querySelector("#btn").click()').
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="evaluate_js",
        text_input=js_code
    )
    return res.message


@tool
def browser_reload(tab_id: Optional[str] = None) -> str:
    """
    Reload (refresh) the current browser tab.
    Use after form submissions, cookie changes, or when a page gets into a stale state.
    Args:
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="reload",
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_get_attribute(
    attribute: str,
    selector: Optional[str] = None,
    element_id: Optional[str] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Read the value of a DOM attribute from a specific element.
    Useful for reading href links, src URLs, data-* identifiers, aria-expanded state, input values, etc.
    Args:
        attribute: Attribute name (e.g. 'href', 'src', 'value', 'data-id', 'aria-expanded', 'placeholder').
        selector: CSS selector of the element.
        element_id: Snapshot element ID.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="get_attribute",
        key=attribute,
        selector=selector,
        element_id=element_id,
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_drag_drop(
    source_selector: str,
    target_selector: str,
    tab_id: Optional[str] = None
) -> str:
    """
    Drag an element from one location and drop it onto another.
    Required for kanban boards, sortable lists, file managers, slider thumbs, and drag-to-reorder UIs.
    Args:
        source_selector: CSS selector of the element to drag (e.g. '.card[data-id="3"]').
        target_selector: CSS selector of the drop target (e.g. '.column[data-status="done"]').
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="drag_drop",
        selector=source_selector,
        url=target_selector,         # url param reused as target_selector
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_upload_file(
    file_path: str,
    selector: Optional[str] = None,
    element_id: Optional[str] = None,
    tab_id: Optional[str] = None
) -> str:
    """
    Set a local file on a file-input element (for uploading attachments, images, or documents).
    The file must already exist at the given server-side path.
    Args:
        file_path: Absolute path to the file on the server (e.g. '/tmp/resume.pdf').
        selector: CSS selector for the file input (e.g. 'input[type="file"]').
        element_id: Snapshot element ID.
        tab_id: Optional target tab ID.
    """
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="upload_file",
        text_input=file_path,
        selector=selector,
        element_id=element_id,
        tab_id=_clean_tab_id(tab_id)
    )
    return res.message


@tool
def browser_new_tab(url: str = "about:blank") -> str:
    """
    Open a new browser tab and navigate to a URL.
    Use when you need to keep the current page open while also loading another site.
    Args:
        url: The URL to open in the new tab (e.g. 'https://github.com').
    """
    ok, msg, tab = browser_service.open_new_tab(user_id=get_current_user_id(), url=url)
    if ok and tab:
        return f"Opened new tab [{tab.id}]: '{tab.title}' at {tab.url}"
    return f"Failed to open new tab: {msg}"


@tool
def browser_mouse_scroll(
    delta_y: int = 500,
    x: Optional[float] = None,
    y: Optional[float] = None,
    delta_x: int = 0
) -> str:
    """
    Dispatch a real mouse wheel event at a specific screen coordinate.
    Use this instead of browser_scroll when the page has overflow containers,
    sidebars, code editors, chat lists, maps, or any element with its own scroll
    context that only responds to genuine wheel events (not window.scrollBy).
    Args:
        delta_y: Pixels to scroll vertically. Positive = down, negative = up (default 500).
        x: Horizontal screen coordinate to place the mouse before scrolling.
           Defaults to viewport centre.
        y: Vertical screen coordinate. Defaults to viewport centre.
        delta_x: Pixels to scroll horizontally (positive = right, default 0).
    """
    coords = f"{x},{y}" if (x is not None and y is not None) else None
    direction = "down" if delta_y >= 0 else "up"
    res = browser_service.execute_action(
        user_id=get_current_user_id(),
        action="mouse_scroll",
        text_input=coords,          # "x,y" or None
        direction=direction,
        pixels=abs(delta_y)
    )
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
    browser_hover,
    browser_wait,
    browser_screenshot,
    browser_go_back,
    browser_go_forward,
    browser_generic_search,
    browser_recover_page,
    browser_paginate,
    # New full-coverage tools
    browser_select_option,
    browser_double_click,
    browser_evaluate_js,
    browser_reload,
    browser_get_attribute,
    browser_drag_drop,
    browser_upload_file,
    browser_new_tab,
    browser_mouse_scroll,
    # Alias tools (kept for backward compat with TOOL_MAP)
    navigate_browser,
    extract_text,
    get_elements,
    click_element,
    type_text,
    press_key,
    wait_for_selector,
    extract_hyperlinks,
    screenshot,
    finish_task,
]
