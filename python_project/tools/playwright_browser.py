"""Interactive Playwright Browser Agent: Headless Chromium browser automation, DOM interaction, and multi-step page actions."""
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from tools.browser_agent import fetch_and_read_webpage, html_to_clean_markdown

MAX_CONTENT_CHARS = 5000
PAGE_TIMEOUT_MS = 15000

def perform_interactive_browser_action(
    url: str,
    action: str = "navigate",
    selector: Optional[str] = None,
    text_input: Optional[str] = None
) -> Dict[str, Any]:
    """
    Spawns a real headless Chromium browser using Playwright, executes actions (navigate, click, type),
    and captures rendered DOM state and interactive links.
    """
    start_time = time.time()
    target_url = url.strip()
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"https://{target_url}"

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page.set_default_timeout(PAGE_TIMEOUT_MS)

            # 1. Navigate to Page
            page.goto(target_url, wait_until="domcontentloaded")

            # 2. Perform requested interactive action
            action_log = f"Navigated to {target_url}"
            if action.lower() in ["type", "fill", "search"] and (selector or text_input):
                input_sel = selector or "input[type='text'], input[type='search'], textarea, input"
                val = text_input or ""
                if val:
                    page.fill(input_sel, val)
                    page.press(input_sel, "Enter")
                    page.wait_for_timeout(1500)
                    action_log = f"Typed '{val}' into '{input_sel}' and submitted"

            elif action.lower() == "click" and selector:
                page.click(selector)
                page.wait_for_timeout(1500)
                action_log = f"Clicked element '{selector}'"

            # 3. Extract page title, current URL, and rendered content
            page_title = page.title() or target_url
            current_url = page.url or target_url
            raw_html = page.content()

            # 4. Extract Top Interactive Links from Rendered DOM
            links: List[Dict[str, str]] = []
            try:
                anchor_elements = page.query_selector_all("a[href]")
                for a in anchor_elements[:8]:
                    href = a.get_attribute("href") or ""
                    link_text = a.inner_text().strip()
                    if href and link_text and not href.startswith("#") and not href.startswith("javascript:"):
                        full_href = urllib.parse.urljoin(current_url, href)
                        links.append({"text": link_text, "url": full_href})
            except Exception:
                pass

            browser.close()

            clean_text = html_to_clean_markdown(raw_html)[:MAX_CONTENT_CHARS]
            duration_ms = int((time.time() - start_time) * 1000)

            formatted_links = ""
            if links:
                formatted_links = "\n\n**Interactive Links Found:**\n" + "\n".join(
                    f"- [{l['text']}]({l['url']})" for l in links
                )

            formatted = (
                f"### 🖥️ Headless Browser: [{page_title}]({current_url})\n\n"
                f"*Action:* `{action_log}` (Executed in {duration_ms}ms)\n\n"
                f"{clean_text}\n"
                f"{formatted_links}"
            )

            return {
                "title": page_title,
                "url": current_url,
                "action": action_log,
                "content": clean_text,
                "links": links,
                "status": "success",
                "execution_time_ms": duration_ms,
                "formatted": formatted
            }

    except Exception as err:
        # Resilient Fallback to HTTP reader if Chromium browser isn't available
        fallback_data = fetch_and_read_webpage(target_url)
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "title": fallback_data.get("title", target_url),
            "url": target_url,
            "action": f"Navigated via HTTP fallback ({str(err)[:60]})",
            "content": fallback_data.get("content", ""),
            "links": [],
            "status": "success",
            "execution_time_ms": duration_ms,
            "formatted": fallback_data.get("formatted", f"Visited {target_url}")
        }

@tool
def interactive_browser_action(
    url: str,
    action: str = "navigate",
    selector: Optional[str] = None,
    text_input: Optional[str] = None
) -> str:
    """
    Spawn a real headless Chromium browser, navigate to any website, execute actions (click elements, type into search inputs, fill forms),
    and extract interactive rendered content and links.
    Args:
        url: The web URL to navigate to (e.g. 'https://www.naukri.com', 'https://github.com/trending').
        action: The action to perform ('navigate', 'click', 'type', 'search').
        selector: Optional CSS selector or element identifier to interact with.
        text_input: Optional text string to type into form/search inputs.
    """
    res = perform_interactive_browser_action(url, action, selector, text_input)
    return res["formatted"]
