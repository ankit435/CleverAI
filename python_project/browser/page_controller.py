"""Page Controller: Semantic action execution (click, type, navigate, scroll, snapshot, screenshot, extract)."""
import base64
import time
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page
from browser.schema import ActionResult, PageSnapshot
from browser.snapshot import snapshot_parser, JS_ACCESSIBILITY_EXTRACTOR
from browser.security_manager import security_manager

DEFAULT_TIMEOUT_MS = 60000

class PageController:
    """Controls individual page navigation and semantic DOM actions."""

    @staticmethod
    def capture_snapshot(page: Page, active_tab_id: str = "tab_1") -> PageSnapshot:
        """Capture live DOM state and convert to structured token-optimized PageSnapshot."""
        title = page.title() or "Untitled"
        url = page.url or "about:blank"

        # Execute JS accessibility extractor
        elements_data: List[Dict[str, Any]] = []
        try:
            elements_data = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
        except Exception:
            pass

        # Extract visible body text
        visible_text = ""
        try:
            visible_text = page.inner_text("body") or ""
        except Exception:
            pass

        return snapshot_parser.build_snapshot(
            title=title,
            url=url,
            active_tab_id=active_tab_id,
            elements_data=elements_data,
            visible_text=visible_text
        )

    @staticmethod
    def navigate(page: Page, url: str) -> ActionResult:
        """Navigate target page to specified URL."""
        start = time.time()
        normalized_url = security_manager.normalize_url(url)
        is_valid, err = security_manager.validate_url(normalized_url)
        if not is_valid:
            return ActionResult(
                action="navigate",
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Navigation rejected: {err}",
                error=err
            )

        try:
            page.goto(normalized_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="navigate",
                status="success",
                duration_ms=duration_ms,
                message=f"Successfully navigated to '{page.url}' ({page.title()})",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="navigate",
                status="error",
                duration_ms=duration_ms,
                message=f"Navigation to '{url}' failed: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def click(page: Page, selector: Optional[str] = None, text: Optional[str] = None, element_id: Optional[int] = None) -> ActionResult:
        """Click element by CSS selector, visible text, or numbered snapshot ID."""
        start = time.time()
        target_locator = None
        target_desc = selector or text or f"element [{element_id}]"

        try:
            if selector:
                target_locator = page.locator(selector).first
            elif text:
                target_locator = page.get_by_text(text, exact=False).first
            elif element_id is not None:
                # Resolve element from current snapshot
                elements = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
                match = next((el for el in elements if el.get("id") == element_id), None)
                if match and match.get("selector"):
                    target_locator = page.locator(match["selector"]).first
                else:
                    return ActionResult(
                        action="click",
                        status="error",
                        duration_ms=int((time.time() - start) * 1000),
                        message=f"Element ID [{element_id}] could not be found in current page snapshot.",
                        error="ELEMENT_NOT_FOUND"
                    )
            else:
                return ActionResult(
                    action="click",
                    status="error",
                    duration_ms=0,
                    message="Click requires 'selector', 'text', or 'element_id'.",
                    error="MISSING_TARGET"
                )

            if not target_locator or target_locator.count() == 0:
                return ActionResult(
                    action="click",
                    status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Target element '{target_desc}' not found on page.",
                    error="ELEMENT_NOT_FOUND"
                )

            target_locator.click(timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(600)  # Short settling delay
            duration_ms = int((time.time() - start) * 1000)

            return ActionResult(
                action="click",
                status="success",
                duration_ms=duration_ms,
                message=f"Clicked on '{target_desc}' successfully.",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="click",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to click '{target_desc}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def type_text(
        page: Page,
        text: str,
        selector: Optional[str] = None,
        element_id: Optional[int] = None,
        clear_first: bool = True,
        press_enter: bool = False
    ) -> ActionResult:
        """Type text into input field by selector or element ID."""
        start = time.time()
        target_locator = None
        target_desc = selector or f"element [{element_id}]" or "focused input"

        try:
            if selector:
                target_locator = page.locator(selector).first
            elif element_id is not None:
                elements = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
                match = next((el for el in elements if el.get("id") == element_id), None)
                if match and match.get("selector"):
                    target_locator = page.locator(match["selector"]).first

            if not target_locator or target_locator.count() == 0:
                # Fallback to focused or first input
                target_locator = page.locator("input:focus, textarea:focus, input[type='text'], input[type='search'], textarea").first

            if target_locator and target_locator.count() > 0:
                if clear_first:
                    target_locator.fill("")
                target_locator.fill(text, timeout=DEFAULT_TIMEOUT_MS)
                if press_enter:
                    target_locator.press("Enter")
                    page.wait_for_timeout(1000)
            else:
                # Generic keyboard type if no input locator found
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")

            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="type",
                status="success",
                duration_ms=duration_ms,
                message=f"Typed '{security_manager.sanitize_page_text(text)}' into '{target_desc}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="type",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to type into '{target_desc}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def press_key(page: Page, key: str) -> ActionResult:
        """Press a keyboard key (Enter, Escape, Tab, ArrowDown, Backspace)."""
        start = time.time()
        try:
            page.keyboard.press(key)
            page.wait_for_timeout(300)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="press_key",
                status="success",
                duration_ms=duration_ms,
                message=f"Pressed key '{key}' successfully.",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="press_key",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to press key '{key}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def scroll(page: Page, direction: str = "down", pixels: int = 500) -> ActionResult:
        """Scroll active page in specified direction."""
        start = time.time()
        try:
            scroll_y = pixels if direction.lower() == "down" else (-pixels if direction.lower() == "up" else 0)
            if direction.lower() == "top":
                page.evaluate("window.scrollTo(0, 0)")
            elif direction.lower() == "bottom":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            else:
                page.evaluate(f"window.scrollBy(0, {scroll_y})")

            page.wait_for_timeout(300)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="scroll",
                status="success",
                duration_ms=duration_ms,
                message=f"Scrolled page {direction} ({pixels}px).",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="scroll",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to scroll page: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def take_screenshot(page: Page, full_page: bool = False) -> ActionResult:
        """Capture screenshot and encode to base64 string."""
        start = time.time()
        try:
            img_bytes = page.screenshot(full_page=full_page, type="jpeg", quality=60)
            b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="screenshot",
                status="success",
                duration_ms=duration_ms,
                message="Screenshot captured successfully.",
                data={"screenshot": b64_str, "full_page": full_page},
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="screenshot",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to capture screenshot: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def go_back(page: Page) -> ActionResult:
        """Navigate back in browser history."""
        start = time.time()
        try:
            page.go_back(wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="go_back",
                status="success",
                duration_ms=duration_ms,
                message=f"Navigated back to '{page.url}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="go_back",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to go back: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def go_forward(page: Page) -> ActionResult:
        """Navigate forward in browser history."""
        start = time.time()
        try:
            page.go_forward(wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="go_forward",
                status="success",
                duration_ms=duration_ms,
                message=f"Navigated forward to '{page.url}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                action="go_forward",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to go forward: {str(e)}",
                error=str(e)
            )
