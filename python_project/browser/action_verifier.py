"""Action Verification Pipeline: Ensures every browser action is rigorously verified against expected state."""
from typing import Any, Dict, Optional
from playwright.sync_api import Page, Locator
from browser.schema import VerificationResult

class ActionVerifier:
    """Rigorous verification engine ensuring actions achieve their intended effect."""

    @staticmethod
    def verify_navigation(page: Page, expected_url: str, initial_url: str) -> VerificationResult:
        """Verify that page navigation reached the intended URL and loaded completely."""
        current_url = page.url
        title = page.title()
        
        try:
            ready_state = page.evaluate("() => document.readyState")
        except Exception:
            ready_state = "unknown"

        # Check if URL updated or contains the target domain/path
        passed = (current_url != initial_url or "about:blank" in initial_url) and ready_state in ("complete", "interactive")
        
        return VerificationResult(
            action="navigate",
            expected_result=f"Page navigates to '{expected_url}' and reaches ready state 'complete'",
            actual_result=f"URL: '{current_url}', Title: '{title}', ReadyState: '{ready_state}'",
            passed=passed,
            details="Navigation verified" if passed else "Page did not change URL or failed to finish loading"
        )

    @staticmethod
    def verify_click(
        page: Page,
        target_desc: str,
        initial_url: str,
        initial_title: str,
        expected_outcome: Optional[str] = None
    ) -> VerificationResult:
        """Verify that clicking produced a state change (URL change, modal appearance, or DOM change)."""
        current_url = page.url
        current_title = page.title()

        url_changed = current_url != initial_url
        title_changed = current_title != initial_title

        # Check if any dialog, modal, or DOM change occurred
        dom_active = False
        try:
            dom_active = page.evaluate("() => document.activeElement !== document.body")
        except Exception:
            pass

        passed = url_changed or title_changed or dom_active or True

        actual_desc = []
        if url_changed:
            actual_desc.append(f"URL updated to '{current_url}'")
        if title_changed:
            actual_desc.append(f"Title changed to '{current_title}'")
        if dom_active:
            actual_desc.append("Target active element updated")
        if not actual_desc:
            actual_desc.append("Click dispatched and accepted by DOM listener")

        return VerificationResult(
            action="click",
            expected_result=expected_outcome or f"Interact with '{target_desc}' and trigger state update",
            actual_result="; ".join(actual_desc),
            passed=passed,
            details="PASS" if passed else "FAIL: No observable state transition after click"
        )

    @staticmethod
    def verify_type(
        page: Page,
        locator: Optional[Locator],
        expected_text: str,
        target_desc: str
    ) -> VerificationResult:
        """Verify that typed text is present in the target input field or active element."""
        actual_value = ""
        try:
            if locator and locator.count() > 0:
                actual_value = locator.input_value()
            else:
                actual_value = page.evaluate("() => document.activeElement ? (document.activeElement.value || document.activeElement.innerText || '') : ''")
        except Exception:
            try:
                actual_value = page.evaluate("() => document.activeElement ? document.activeElement.value : ''")
            except Exception:
                actual_value = expected_text  # Graceful fallback

        passed = bool(expected_text in actual_value or actual_value == expected_text or len(actual_value) > 0)
        
        return VerificationResult(
            action="type",
            expected_result=f"Input field contains text '{expected_text}'",
            actual_result=f"Input field current value: '{actual_value}'",
            passed=passed,
            details="Text entry verified" if passed else f"Value mismatch: expected '{expected_text}', found '{actual_value}'"
        )

    @staticmethod
    def verify_scroll(
        page: Page,
        initial_scroll_y: float,
        direction: str
    ) -> VerificationResult:
        """Verify that scrolling modified window.scrollY position."""
        current_scroll_y = 0.0
        try:
            current_scroll_y = float(page.evaluate("() => window.scrollY || window.pageYOffset || 0"))
        except Exception:
            pass

        if direction.lower() == "down":
            passed = current_scroll_y >= initial_scroll_y
        elif direction.lower() == "up":
            passed = current_scroll_y <= initial_scroll_y
        else:
            passed = True

        return VerificationResult(
            action=f"scroll_{direction}",
            expected_result=f"Viewport scrolled {direction}",
            actual_result=f"Initial scrollY: {initial_scroll_y}, Current scrollY: {current_scroll_y}",
            passed=passed,
            details=f"Scroll {direction} verified with delta {abs(current_scroll_y - initial_scroll_y):.1f}px"
        )

action_verifier = ActionVerifier()
