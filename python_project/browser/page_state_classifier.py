"""Page State Classifier: Multi-signal classification for web pages."""
import re
from typing import Optional
from playwright.sync_api import Page
from browser.schema import PageState

class PageStateClassifier:
    """Classifies page operational state using HTTP status, URL, title, DOM structure, and visible text."""

    @staticmethod
    def classify(page: Page, visible_text: str = "", http_status: Optional[int] = None) -> PageState:
        """Classify page into standard PageState enum."""
        if not page:
            return PageState.UNKNOWN

        url = (page.url or "").lower()
        title = (page.title() or "").lower()
        text = visible_text.lower() if visible_text else ""

        # 1. HTTP Status Signals
        if http_status:
            if http_status == 404:
                return PageState.NOT_FOUND
            elif http_status in (401, 403):
                return PageState.ACCESS_DENIED
            elif http_status >= 500:
                return PageState.ERROR

        # 2. Loading State
        try:
            ready_state = page.evaluate("() => document.readyState")
            if ready_state == "loading":
                return PageState.LOADING
        except Exception:
            pass

        # 3. Captcha / Bot Block Signals
        captcha_indicators = [
            "verify you are human", "robot or human", "captcha", "hcaptcha",
            "recaptcha", "cloudflare ray id", "checking your browser", "turnstile",
            "access to this page has been denied", "bot detection"
        ]
        if any(c in title or c in text for c in captcha_indicators):
            return PageState.CAPTCHA

        # 4. Access Denied / Forbidden
        access_denied_indicators = [
            "403 forbidden", "access denied", "permission denied", "not authorized",
            "you don't have permission to access", "forbidden"
        ]
        if any(ad in title or ad in text for ad in access_denied_indicators):
            return PageState.ACCESS_DENIED

        # 5. Page Not Found (404 / Moved / Deleted)
        not_found_indicators = [
            "404 not found", "page not found", "page cannot be found",
            "moved or deleted", "page does not exist", "the page you requested was not found",
            "item not found", "looks like you are lost", "error 404"
        ]
        if any(nf in title or nf in text for nf in not_found_indicators):
            return PageState.NOT_FOUND

        # 6. Login / Authentication Required
        login_indicators = [
            "please sign in to continue", "login required", "sign in to your account",
            "session expired", "please log in", "authentication required"
        ]
        if any(li in title or li in text for li in login_indicators) and "signup" not in title and "shop" not in title:
            if "login" in url or "signin" in url or "auth" in url:
                return PageState.LOGIN_REQUIRED

        # 7. Internal Server Error / Application Error
        error_indicators = [
            "500 internal server error", "502 bad gateway", "503 service unavailable",
            "504 gateway timeout", "something went wrong on our end", "application error"
        ]
        if any(err in title or err in text for err in error_indicators):
            return PageState.ERROR

        # 8. Empty / Blank Page
        if url in ("about:blank", "about:srcdoc") or (not title and not text.strip()):
            return PageState.EMPTY

        return PageState.VALID

page_state_classifier = PageStateClassifier()
