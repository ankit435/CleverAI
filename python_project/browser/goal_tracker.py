"""Autonomous Goal Completion & Pagination / Infinite Scroll Tracker."""
from typing import Any, Dict, List, Optional, Set, Tuple
from playwright.sync_api import Page
from browser.schema import GoalTrackingState, PageSnapshot
from browser.snapshot import JS_ACCESSIBILITY_EXTRACTOR

class GoalTracker:
    """Tracks autonomous multi-step subgoals, pagination detection, and deduplicated item collection."""

    @staticmethod
    def is_exhaustive_request(prompt: str) -> bool:
        """Determine if prompt requests all / complete / every item."""
        lower = prompt.lower()
        exhaustive_terms = ["all", "every", "complete list", "all results", "everything", "all repositories", "all jobs", "all products"]
        return any(term in lower for term in exhaustive_terms)

    @staticmethod
    def detect_pagination_or_next(page: Page, snapshot: Optional[PageSnapshot] = None) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Detect if the current page has a 'Next' button, pagination link, or 'Load More' element.
        Returns: (has_next, next_selector, next_element_id)
        """
        try:
            # Check for common next / load more buttons
            elements: List[Dict[str, Any]] = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
            for el in elements:
                name_or_text = (el.get("name") or el.get("text") or "").lower()
                aria_label = (el.get("aria_attributes") or {}).get("aria-label", "").lower()
                
                if any(kw in name_or_text or kw in aria_label for kw in ["next", "next page", "load more", "more results", "view more", "show more", ">", "›", "»"]):
                    if el.get("is_clickable") and el.get("enabled", True):
                        return True, el.get("selector"), el.get("id")
        except Exception:
            pass

        return False, None, None

    @staticmethod
    def extract_structured_list_items(page: Page) -> List[Dict[str, Any]]:
        """Extract visible repeated list items, cards, or search result blocks from the page."""
        items: List[Dict[str, Any]] = []
        try:
            js_extract_items = """
            (() => {
                const results = [];
                // Look for common list item or card selectors
                const candidates = document.querySelectorAll('li, article, .item, .card, .s-result-item, .repository-item, tr');
                candidates.forEach((el, i) => {
                    const text = (el.innerText || '').trim();
                    if (text.length > 10 && text.length < 500) {
                        const link = el.querySelector('a');
                        results.push({
                            index: i + 1,
                            text: text.replace(/\\s+/g, ' ').slice(0, 200),
                            href: link ? link.href : undefined
                        });
                    }
                });
                return results.slice(0, 30);
            })()
            """
            items = page.evaluate(js_extract_items)
        except Exception:
            pass
        return items

    @staticmethod
    def deduplicate_items(existing_items: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate extracted results by text hash or href."""
        seen_keys: Set[str] = set()
        deduped: List[Dict[str, Any]] = []

        for it in existing_items + new_items:
            key = (it.get("href") or it.get("text") or "").strip().lower()
            if key and key not in seen_keys:
                seen_keys.add(key)
                deduped.append(it)

        return deduped

goal_tracker = GoalTracker()
