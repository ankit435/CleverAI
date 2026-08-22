"""Page Controller: Semantic action execution with multi-strategy resolution and rigorous verification."""
import base64
import time
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page, Locator
from browser.schema import ActionResult, PageSnapshot, ResolutionStrategy
from browser.page_observer import page_observer
from browser.action_executor import action_executor
from browser.recovery_engine import recovery_engine

class PageController:
    """Controls individual page navigation and semantic DOM actions with multi-strategy resolution and verification."""

    @staticmethod
    def capture_snapshot(page: Page, active_tab_id: str = "tab_1") -> PageSnapshot:
        """Capture live DOM state and convert to structured token-optimized PageSnapshot."""
        return page_observer.observe(page, active_tab_id=active_tab_id)

    @staticmethod
    def navigate(page: Page, url: str) -> ActionResult:
        """Navigate target page to specified URL with dynamic wait and verification."""
        return action_executor.navigate(page, url)

    @staticmethod
    def click(
        page: Page,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        element_id: Optional[Any] = None,
        role: Optional[str] = None,
        name: Optional[str] = None,
        coordinates: Optional[Tuple[float, float]] = None
    ) -> ActionResult:
        """Click element via target resolver with state tracking and verification."""
        return action_executor.click(
            page=page,
            element_id=element_id,
            selector=selector,
            text=text,
            role=role,
            name=name,
            coordinates=coordinates
        )

    @staticmethod
    def type_text(
        page: Page,
        text: str,
        selector: Optional[str] = None,
        element_id: Optional[Any] = None,
        clear_first: bool = True,
        press_enter: bool = False
    ) -> ActionResult:
        """Type text into input field with multi-strategy resolution and verification."""
        return action_executor.type_text(
            page=page,
            text=text,
            element_id=element_id,
            selector=selector,
            clear_first=clear_first,
            press_enter=press_enter
        )

    @staticmethod
    def press_key(page: Page, key: str) -> ActionResult:
        """Press a keyboard key."""
        return action_executor.press_key(page, key)

    @staticmethod
    def scroll(page: Page, direction: str = "down", pixels: int = 500) -> ActionResult:
        """Scroll active page with dynamic verification."""
        return action_executor.scroll(page, direction=direction, pixels=pixels)

    @staticmethod
    def hover(page: Page, selector: Optional[str] = None, element_id: Optional[Any] = None) -> ActionResult:
        """Hover over an element."""
        return action_executor.hover(page, selector=selector, element_id=element_id)

    @staticmethod
    def wait(page: Page, seconds: float = 1.0) -> ActionResult:
        """Wait for dynamic state."""
        return action_executor.wait(page, seconds=seconds)

    @staticmethod
    def recover_invalid_page(page: Page, user_goal: str) -> ActionResult:
        """Generic 404 / Invalid Page recovery."""
        return recovery_engine.recover_from_invalid_page(page, user_goal)

    @staticmethod
    def generic_search(page: Page, query: str) -> ActionResult:
        """Generic on-page search discovery and execution."""
        return recovery_engine.execute_generic_search(page, query)

    @staticmethod
    def take_screenshot(page: Page, full_page: bool = False) -> ActionResult:
        """Capture screenshot and encode to base64 string."""
        start = time.time()
        try:
            img_bytes = page.screenshot(full_page=full_page, type="jpeg", quality=60)
            b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True,
                action="screenshot",
                target="page",
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
                success=False,
                action="screenshot",
                target="page",
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
                success=True,
                action="go_back",
                target="history",
                status="success",
                duration_ms=duration_ms,
                message=f"Navigated back to '{page.url}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="go_back",
                target="history",
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
                success=True,
                action="go_forward",
                target="history",
                status="success",
                duration_ms=duration_ms,
                message=f"Navigated forward to '{page.url}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="go_forward",
                target="history",
                status="error",
                duration_ms=duration_ms,
                message=f"Failed to go forward: {str(e)}",
                error=str(e)
            )
