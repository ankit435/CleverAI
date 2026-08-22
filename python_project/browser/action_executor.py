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
        """Scroll page dynamically and verify offset delta."""
        start = time.time()
        initial_scroll_y = 0.0
        try:
            initial_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
        except Exception:
            pass

        before_state = f"scrollY={initial_scroll_y}"

        try:
            scroll_y = pixels if direction.lower() == "down" else (-pixels if direction.lower() == "up" else 0)
            if direction.lower() == "top":
                page.evaluate("window.scrollTo(0, 0)")
            elif direction.lower() == "bottom":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            else:
                page.evaluate(f"window.scrollBy(0, {scroll_y})")

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
                message=f"Scrolled {direction} ({pixels}px) [Verification: {verification.details}]",
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

action_executor = ActionExecutor()
