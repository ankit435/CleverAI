"""Recovery Engine: Generic autonomous recovery for navigation errors, 404s, stale elements, and unknown site search."""
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page, Locator
from browser.schema import PageState, PageSnapshot, ActionResult, ResolutionStrategy
from browser.page_observer import page_observer
from browser.action_verifier import action_verifier

class RecoveryEngine:
    """Classifies browser failures and executes autonomous recovery pipelines without website-specific rules."""

    @staticmethod
    def discover_search_input(page: Page) -> Tuple[Optional[Locator], str]:
        """
        Generic search discovery on unknown websites:
        Inspects page semantics to locate the primary search input using:
        role, aria-label, placeholder, name, type='search', or form semantics.
        """
        # 1. Standard search roles & attributes
        search_selectors = [
            "input[type='search']",
            "input[aria-label*='search' i]",
            "input[placeholder*='search' i]",
            "input[name='q']",
            "input[name='query']",
            "input[name='search']",
            "input[name='k']",
            "input[name='keyword']",
            "input[title*='search' i]",
            "input[id*='search' i]",
            "form[role='search'] input",
            "header input[type='text']"
        ]
        for sel in search_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    return loc, sel
            except Exception:
                continue

        # 2. General text input fallback in header/nav
        try:
            loc = page.locator("header input, nav input, div[role='search'] input").first
            if loc.count() > 0 and loc.is_visible():
                return loc, "header/nav input"
        except Exception:
            pass

        return None, ""

    @staticmethod
    def recover_from_invalid_page(page: Page, user_goal: str) -> ActionResult:
        """
        Generic 404 / Invalid Page Recovery:
        1. Find Home / Logo navigation link on current page.
        2. Return to usable root page.
        3. Discover search capability and prepare for user goal.
        """
        # Look for home link or brand logo
        home_selectors = [
            "a[href='/']",
            "a[aria-label*='home' i]",
            "a[title*='home' i]",
            "a.logo",
            "header a:has(img)",
            "header a:first-child"
        ]
        for sel in home_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=10000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    return ActionResult(
                        success=True,
                        action="recover_navigation",
                        target=sel,
                        status="success",
                        message=f"Recovered from invalid page by navigating back to Home via '{sel}'",
                        current_url=page.url,
                        current_title=page.title()
                    )
            except Exception:
                continue

        # Fallback: Go back in history
        try:
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            return ActionResult(
                success=True,
                action="recover_navigation",
                target="history_back",
                status="success",
                message=f"Recovered from invalid page by navigating back to '{page.url}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="recover_navigation",
                target="history_back",
                status="error",
                message=f"Could not recover from invalid page: {str(e)}",
                error=str(e)
            )

    @staticmethod
    def execute_generic_search(page: Page, query: str) -> ActionResult:
        """
        Autonomously locate search input, fill query, and submit on any unknown website.
        """
        loc, sel = RecoveryEngine.discover_search_input(page)
        if not loc:
            return ActionResult(
                success=False,
                action="generic_search",
                target=query,
                status="error",
                message="No search input field detected on active page.",
                error="SEARCH_INPUT_NOT_FOUND"
            )

        try:
            loc.fill("")
            loc.fill(query)
            loc.press("Enter")
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            return ActionResult(
                success=True,
                action="generic_search",
                target=f"input='{sel}' query='{query}'",
                status="success",
                message=f"Executed generic search for '{query}' using '{sel}'",
                current_url=page.url,
                current_title=page.title()
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="generic_search",
                target=query,
                status="error",
                message=f"Search submission failed: {str(e)}",
                error=str(e)
            )

recovery_engine = RecoveryEngine()
