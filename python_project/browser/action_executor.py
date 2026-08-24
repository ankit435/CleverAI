"""Action Executor: Generic semantic action execution with state tracking and verification."""
import time
import base64
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page, Locator
from browser.schema import ActionResult, VerificationResult, VerificationType, TargetConfidence, ResolutionStrategy
from browser.target_resolver import target_resolver
from browser.action_verifier import action_verifier
from browser.security_manager import security_manager

DEFAULT_TIMEOUT_MS = 60000

class ActionExecutor:
    """Executes generic browser interactions and records before/after state with verification."""

    @staticmethod
    def navigate(page: Page, url: str) -> ActionResult:
        """Navigate to URL with before/after state and verification."""
        start = time.time()
        before_state = f"url={page.url} title={page.title()}"
        normalized = security_manager.normalize_url(url)
        is_valid, err = security_manager.validate_url(normalized)
        if not is_valid:
            return ActionResult(
                success=False,
                action="navigate",
                target=url,
                status="error",
                before_state=before_state,
                after_state=before_state,
                state_changed=False,
                duration_ms=int((time.time() - start) * 1000),
                message=f"Navigation rejected: {err}",
                error=err
            )

        try:
            page.goto(normalized, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            after_state = f"url={page.url} title={page.title()}"
            verification = action_verifier.verify_navigation(page, expected_url=normalized, initial_url=before_state)
            duration_ms = int((time.time() - start) * 1000)

            return ActionResult(
                success=verification.passed,
                action="navigate",
                target=normalized,
                status="success" if verification.passed else "error",
                before_state=before_state,
                after_state=after_state,
                state_changed=(before_state != after_state),
                duration_ms=duration_ms,
                message=f"Navigated to '{page.url}' ({page.title()}) [Verification: {verification.details}]",
                current_url=page.url,
                current_title=page.title(),
                verification=verification
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="navigate",
                target=url,
                status="error",
                before_state=before_state,
                after_state=f"url={page.url} title={page.title()}",
                state_changed=False,
                duration_ms=duration_ms,
                message=f"Navigation to '{url}' failed: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def click(
        page: Page,
        element_id: Optional[Any] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        role: Optional[str] = None,
        name: Optional[str] = None,
        coordinates: Optional[Tuple[float, float]] = None
    ) -> ActionResult:
        """Click element via target resolver with state tracking and verification."""
        start = time.time()
        before_state = f"url={page.url} title={page.title()}"
        initial_url = page.url
        initial_title = page.title()

        locator, strategy, target_desc, coords, confidence = target_resolver.resolve(
            page=page,
            element_id=element_id,
            selector=selector,
            text=text,
            role=role,
            name=name,
            coordinates=coordinates
        )

        try:
            if locator and locator.count() > 0:
                locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
                locator.click(timeout=DEFAULT_TIMEOUT_MS)
            elif coords:
                page.mouse.click(coords[0], coords[1])
            else:
                return ActionResult(
                    success=False,
                    action="click",
                    target=target_desc,
                    status="error",
                    before_state=before_state,
                    after_state=before_state,
                    state_changed=False,
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Target element could not be resolved across strategies: {target_desc}",
                    error="TARGET_NOT_RESOLVED",
                    resolution_confidence=confidence,
                    resolution_method=strategy.value
                )

            after_state = f"url={page.url} title={page.title()}"
            verification = action_verifier.verify_click(
                page=page,
                target_desc=target_desc,
                initial_url=initial_url,
                initial_title=initial_title
            )

            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=verification.passed,
                action="click",
                target=target_desc,
                status="success" if verification.passed else "error",
                before_state=before_state,
                after_state=after_state,
                state_changed=(before_state != after_state),
                duration_ms=duration_ms,
                message=f"Clicked '{target_desc}' via {strategy.value} (Confidence: {confidence.confidence}) [Verification: {verification.details}]",
                current_url=page.url,
                current_title=page.title(),
                verification=verification,
                resolution_confidence=confidence,
                resolution_method=strategy.value
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="click",
                target=target_desc,
                status="error",
                before_state=before_state,
                after_state=f"url={page.url} title={page.title()}",
                state_changed=False,
                duration_ms=duration_ms,
                message=f"Failed to click '{target_desc}': {str(e)}",
                error=str(e),
                resolution_confidence=confidence,
                resolution_method=strategy.value
            )

    @staticmethod
    def type_text(
        page: Page,
        text: str,
        element_id: Optional[Any] = None,
        selector: Optional[str] = None,
        clear_first: bool = True,
        press_enter: bool = False
    ) -> ActionResult:
        """Type text into input element with verification."""
        start = time.time()
        before_state = f"url={page.url} title={page.title()}"
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page,
            element_id=element_id,
            selector=selector
        )

        try:
            if not locator or locator.count() == 0:
                locator = page.locator("input:focus, textarea:focus, input[type='text'], input[type='search'], textarea").first

            if locator and locator.count() > 0:
                locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
                if clear_first:
                    locator.fill("")
                locator.fill(text, timeout=DEFAULT_TIMEOUT_MS)
                if press_enter:
                    locator.press("Enter")
            else:
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")

            after_state = f"url={page.url} title={page.title()}"
            verification = action_verifier.verify_type(
                page=page,
                locator=locator,
                expected_text=text,
                target_desc=target_desc
            )

            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=verification.passed,
                action="type",
                target=target_desc,
                status="success" if verification.passed else "error",
                before_state=before_state,
                after_state=after_state,
                state_changed=True,
                duration_ms=duration_ms,
                message=f"Typed text into '{target_desc}' [Verification: {verification.details}]",
                current_url=page.url,
                current_title=page.title(),
                verification=verification,
                resolution_confidence=confidence,
                resolution_method=strategy.value
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="type",
                target=target_desc,
                status="error",
                before_state=before_state,
                after_state=before_state,
                state_changed=False,
                duration_ms=duration_ms,
                message=f"Failed to type into '{target_desc}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def scroll(page: Page, direction: str = "down", pixels: int = 500) -> ActionResult:
        """Scroll page using real mouse wheel events (fallback to JS for top/bottom jumps)."""
        start = time.time()
        initial_scroll_y = 0.0
        try:
            initial_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
        except Exception:
            pass

        before_state = f"scrollY={initial_scroll_y}"

        try:
            lower_dir = direction.lower()
            if lower_dir == "top":
                # Jump to top — JS is the right tool here
                page.evaluate("window.scrollTo(0, 0)")
            elif lower_dir == "bottom":
                # Jump to bottom
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            else:
                # Use real mouse wheel events so sites with custom wheel listeners
                # (infinite scroll, lazy-load, rich editors) respond correctly.
                delta_y = pixels if lower_dir == "down" else -pixels
                # Move mouse to centre of viewport first so the wheel event lands
                # on the scrollable element rather than a fixed overlay.
                try:
                    vw = page.evaluate("() => window.innerWidth")
                    vh = page.evaluate("() => window.innerHeight")
                    page.mouse.move(vw / 2, vh / 2)
                except Exception:
                    pass
                page.mouse.wheel(0, delta_y)
                # Small settle wait so lazy-load callbacks can fire
                try:
                    page.wait_for_timeout(300)
                except Exception:
                    pass

            verification = action_verifier.verify_scroll(page, initial_scroll_y=initial_scroll_y, direction=direction)
            new_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
            after_state = f"scrollY={new_scroll_y}"
            duration_ms = int((time.time() - start) * 1000)

            return ActionResult(
                success=verification.passed,
                action="scroll",
                target=f"direction={direction} pixels={pixels}",
                status="success",
                before_state=before_state,
                after_state=after_state,
                state_changed=(before_state != after_state),
                duration_ms=duration_ms,
                message=f"Mouse-wheel scrolled {direction} ({pixels}px) [Verification: {verification.details}]",
                current_url=page.url,
                current_title=page.title(),
                verification=verification
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=False,
                action="scroll",
                target=direction,
                status="error",
                before_state=before_state,
                after_state=before_state,
                state_changed=False,
                duration_ms=duration_ms,
                message=f"Failed to scroll page: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def hover(page: Page, selector: Optional[str] = None, element_id: Optional[Any] = None) -> ActionResult:
        """Hover over an interactive target."""
        start = time.time()
        before_state = f"url={page.url}"
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector
        )
        try:
            if locator and locator.count() > 0:
                locator.hover(timeout=DEFAULT_TIMEOUT_MS)
                duration_ms = int((time.time() - start) * 1000)
                return ActionResult(
                    success=True,
                    action="hover",
                    target=target_desc,
                    status="success",
                    before_state=before_state,
                    after_state=before_state,
                    state_changed=True,
                    duration_ms=duration_ms,
                    message=f"Hovered over '{target_desc}' successfully.",
                    current_url=page.url,
                    current_title=page.title(),
                    resolution_confidence=confidence,
                    resolution_method=strategy.value
                )
            else:
                return ActionResult(
                    success=False,
                    action="hover",
                    target=target_desc,
                    status="error",
                    before_state=before_state,
                    after_state=before_state,
                    state_changed=False,
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Hover target not found: {target_desc}",
                    error="ELEMENT_NOT_FOUND"
                )
        except Exception as e:
            return ActionResult(
                success=False,
                action="hover",
                target=target_desc,
                status="error",
                before_state=before_state,
                after_state=before_state,
                state_changed=False,
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to hover over '{target_desc}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def press_key(page: Page, key: str) -> ActionResult:
        """Press keyboard key."""
        start = time.time()
        before_state = f"url={page.url}"
        try:
            page.keyboard.press(key)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True,
                action="press_key",
                target=key,
                status="success",
                before_state=before_state,
                after_state=f"url={page.url}",
                state_changed=True,
                duration_ms=duration_ms,
                message=f"Pressed key '{key}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="press_key",
                target=key,
                status="error",
                before_state=before_state,
                after_state=before_state,
                state_changed=False,
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to press key '{key}': {str(e)}",
                error=str(e)
            )

    @staticmethod
    def wait(page: Page, seconds: float = 1.0) -> ActionResult:
        """Wait for dynamic DOM state or specified timeout."""
        start = time.time()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True,
                action="wait",
                target=f"{seconds}s",
                status="success",
                duration_ms=duration_ms,
                message=f"Waited for dynamic page ready state ({duration_ms}ms)",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="wait",
                target=f"{seconds}s",
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Wait interrupted: {str(e)}",
                error=str(e)
            )

    # ------------------------------------------------------------------
    # New actions required for full-coverage website automation
    # ------------------------------------------------------------------

    @staticmethod
    def select_option(
        page: Page,
        value: str,
        selector: Optional[str] = None,
        element_id: Optional[Any] = None
    ) -> ActionResult:
        """Select an option from a <select> dropdown element by value or label."""
        start = time.time()
        before_state = f"url={page.url}"
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector
        )
        try:
            sel_loc = locator if (locator and locator.count() > 0) else page.locator("select").first
            sel_loc.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
            # Try by value first, then by label text
            try:
                sel_loc.select_option(value=value, timeout=DEFAULT_TIMEOUT_MS)
            except Exception:
                sel_loc.select_option(label=value, timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="select_option", target=target_desc, status="success",
                before_state=before_state, after_state=f"url={page.url}", state_changed=True,
                duration_ms=duration_ms,
                message=f"Selected option '{value}' in '{target_desc}'",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="select_option", target=target_desc, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to select option '{value}': {str(e)}", error=str(e)
            )

    @staticmethod
    def mouse_scroll(
        page: Page,
        x: Optional[float] = None,
        y: Optional[float] = None,
        delta_x: float = 0,
        delta_y: float = 500
    ) -> ActionResult:
        """
        Dispatch a mouse wheel event at a specific (x, y) screen coordinate.
        Ideal for scrolling inside overflow containers, sidebars, code editors,
        chat message lists, and any element that has its own scroll context.
        """
        start = time.time()
        initial_scroll_y = 0.0
        try:
            initial_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
        except Exception:
            pass

        try:
            # If coordinates not provided, default to viewport centre
            if x is None or y is None:
                vw = page.evaluate("() => window.innerWidth") or 800
                vh = page.evaluate("() => window.innerHeight") or 600
                x = x if x is not None else vw / 2
                y = y if y is not None else vh / 2

            page.mouse.move(x, y)
            page.mouse.wheel(delta_x, delta_y)

            try:
                page.wait_for_timeout(300)
            except Exception:
                pass

            new_scroll_y = 0.0
            try:
                new_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
            except Exception:
                pass

            direction_label = "down" if delta_y > 0 else ("up" if delta_y < 0 else "right" if delta_x > 0 else "left")
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True,
                action="mouse_scroll",
                target=f"({x:.0f},{y:.0f})",
                status="success",
                before_state=f"scrollY={initial_scroll_y}",
                after_state=f"scrollY={new_scroll_y}",
                state_changed=True,
                duration_ms=duration_ms,
                message=(
                    f"Mouse-wheel scrolled {direction_label} at ({x:.0f},{y:.0f}) "
                    f"[delta_x={delta_x}, delta_y={delta_y}]"
                ),
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="mouse_scroll",
                target=f"({x},{y})",
                status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Mouse scroll failed: {str(e)}",
                error=str(e)
            )
        start = time.time()
        before_state = f"url={page.url}"
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector
        )
        try:
            sel_loc = locator if (locator and locator.count() > 0) else page.locator("select").first
            sel_loc.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
            # Try by value first, then by label text
            try:
                sel_loc.select_option(value=value, timeout=DEFAULT_TIMEOUT_MS)
            except Exception:
                sel_loc.select_option(label=value, timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="select_option", target=target_desc, status="success",
                before_state=before_state, after_state=f"url={page.url}", state_changed=True,
                duration_ms=duration_ms,
                message=f"Selected option '{value}' in '{target_desc}'",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="select_option", target=target_desc, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to select option '{value}': {str(e)}", error=str(e)
            )

    @staticmethod
    def double_click(
        page: Page,
        selector: Optional[str] = None,
        element_id: Optional[Any] = None,
        text: Optional[str] = None
    ) -> ActionResult:
        """Double-click an element (text selection, rich editors, file rename)."""
        start = time.time()
        before_state = f"url={page.url}"
        locator, strategy, target_desc, coords, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector, text=text
        )
        try:
            if locator and locator.count() > 0:
                locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
                locator.dbl_click(timeout=DEFAULT_TIMEOUT_MS)
            elif coords:
                page.mouse.dblclick(coords[0], coords[1])
            else:
                return ActionResult(
                    success=False, action="double_click", target=target_desc, status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Element not found for double-click: {target_desc}",
                    error="ELEMENT_NOT_FOUND"
                )
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="double_click", target=target_desc, status="success",
                before_state=before_state, after_state=f"url={page.url}", state_changed=True,
                duration_ms=duration_ms,
                message=f"Double-clicked '{target_desc}'",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="double_click", target=target_desc, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to double-click '{target_desc}': {str(e)}", error=str(e)
            )

    @staticmethod
    def evaluate_js(page: Page, js_code: str) -> ActionResult:
        """Evaluate a JavaScript expression/statement in the page context."""
        start = time.time()
        try:
            result = page.evaluate(js_code)
            duration_ms = int((time.time() - start) * 1000)
            result_str = str(result)[:2000] if result is not None else "null"
            return ActionResult(
                success=True, action="evaluate_js", target="page", status="success",
                duration_ms=duration_ms,
                message=f"JavaScript result: {result_str}",
                data={"result": result_str},
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="evaluate_js", target="page", status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"JavaScript execution failed: {str(e)}", error=str(e)
            )

    @staticmethod
    def reload(page: Page) -> ActionResult:
        """Reload / refresh the current page."""
        start = time.time()
        before_url = page.url
        try:
            page.reload(wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="reload", target=before_url, status="success",
                before_state=f"url={before_url}", after_state=f"url={page.url}",
                state_changed=True, duration_ms=duration_ms,
                message=f"Page reloaded: '{page.title()}' ({page.url})",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="reload", target=before_url, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to reload page: {str(e)}", error=str(e)
            )

    @staticmethod
    def get_attribute(
        page: Page,
        attribute: str,
        selector: Optional[str] = None,
        element_id: Optional[Any] = None
    ) -> ActionResult:
        """Read the value of a named DOM attribute from a specific element."""
        start = time.time()
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector
        )
        try:
            if not locator or locator.count() == 0:
                return ActionResult(
                    success=False, action="get_attribute", target=target_desc, status="error",
                    duration_ms=int((time.time() - start) * 1000),
                    message=f"Element not found: {target_desc}", error="ELEMENT_NOT_FOUND"
                )
            value = locator.first.get_attribute(attribute)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="get_attribute", target=target_desc, status="success",
                duration_ms=duration_ms,
                message=f"'{attribute}' of '{target_desc}' = '{value}'",
                data={"attribute": attribute, "value": value},
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="get_attribute", target=target_desc, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to get attribute '{attribute}': {str(e)}", error=str(e)
            )

    @staticmethod
    def drag_drop(page: Page, source_selector: str, target_selector: str) -> ActionResult:
        """Drag an element and drop it onto another (kanban boards, sortable lists, sliders)."""
        start = time.time()
        try:
            page.drag_and_drop(source_selector, target_selector, timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="drag_drop",
                target=f"{source_selector} → {target_selector}",
                status="success", duration_ms=duration_ms,
                message=f"Dragged '{source_selector}' and dropped onto '{target_selector}'",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="drag_drop",
                target=f"{source_selector} → {target_selector}",
                status="error", duration_ms=int((time.time() - start) * 1000),
                message=f"Drag-and-drop failed: {str(e)}", error=str(e)
            )

    @staticmethod
    def upload_file(
        page: Page,
        file_path: str,
        selector: Optional[str] = None,
        element_id: Optional[Any] = None
    ) -> ActionResult:
        """Set a local file on a file-input element."""
        import os
        start = time.time()
        if not os.path.exists(file_path):
            return ActionResult(
                success=False, action="upload_file", target=file_path, status="error",
                duration_ms=0,
                message=f"File not found: '{file_path}'", error="FILE_NOT_FOUND"
            )
        locator, strategy, target_desc, _, confidence = target_resolver.resolve(
            page=page, element_id=element_id, selector=selector
        )
        try:
            file_loc = (
                locator if (locator and locator.count() > 0)
                else page.locator("input[type='file']").first
            )
            file_loc.wait_for(state="attached", timeout=DEFAULT_TIMEOUT_MS)
            file_loc.set_input_files(file_path, timeout=DEFAULT_TIMEOUT_MS)
            duration_ms = int((time.time() - start) * 1000)
            return ActionResult(
                success=True, action="upload_file", target=target_desc, status="success",
                duration_ms=duration_ms,
                message=f"File '{os.path.basename(file_path)}' set on '{target_desc}'",
                current_url=page.url, current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False, action="upload_file", target=target_desc, status="error",
                duration_ms=int((time.time() - start) * 1000),
                message=f"Failed to upload file: {str(e)}", error=str(e)
            )

action_executor = ActionExecutor()
