"""Multi-Strategy Target Resolver for Autonomous Browser Interaction.

Resolves interactive targets strictly following the priority order:
1. Snapshot Element ID Reference (e1, e2, 15)
2. Accessibility Role / Accessible Name
3. Stable DOM Attributes (data-testid, id, name, aria-label)
4. Visible Text (Exact, then Substring)
5. DOM Hierarchy / Container Context
6. Semantic Relationship
7. Screenshot / Visual Analysis & Bounding Box
8. Coordinate Fallback (Last Resort)
"""
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page, Locator
from browser.schema import ResolutionStrategy, TargetConfidence, InteractiveElement, PageSnapshot
from browser.snapshot import JS_ACCESSIBILITY_EXTRACTOR

class TargetResolver:
    """Multi-strategy target resolution engine with confidence scoring."""

    @classmethod
    def resolve(
        cls,
        page: Page,
        element_id: Optional[Any] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        role: Optional[str] = None,
        name: Optional[str] = None,
        coordinates: Optional[Tuple[float, float]] = None,
        snapshot: Optional[PageSnapshot] = None
    ) -> Tuple[Optional[Locator], ResolutionStrategy, str, Optional[Tuple[float, float]], TargetConfidence]:
        """
        Attempt resolution across all strategies in strict priority order.
        Returns: (Locator, ResolutionStrategy, description, optional_coordinates, TargetConfidence)
        """
        # Normalize element_id if string like "e15" or integer 15 or "none"
        norm_elem_id = None
        if element_id is not None:
            raw_str = str(element_id).lower().strip()
            if raw_str not in ("none", "null", "undefined", "", "0"):
                if raw_str.startswith("e") and raw_str[1:].isdigit():
                    norm_elem_id = int(raw_str[1:])
                elif raw_str.isdigit():
                    norm_elem_id = int(raw_str)

        # 1. Strategy 1: Snapshot Element ID Reference (e.g. e1, 15)
        if norm_elem_id is not None:
            # Check snapshot first if passed
            elements = snapshot.elements if snapshot else []
            if not elements:
                try:
                    elements_raw = page.evaluate(JS_ACCESSIBILITY_EXTRACTOR)
                    elements = [InteractiveElement(**el) for el in elements_raw if isinstance(el, dict) and "id" in el]
                except Exception:
                    pass

            target_el = next((e for e in elements if e.id == norm_elem_id or e.element_id == f"e{norm_elem_id}"), None)
            if target_el:
                # Try selector
                if target_el.selector:
                    try:
                        loc = page.locator(target_el.selector).first
                        if loc.count() > 0:
                            desc = f"snapshot_element_id=[{norm_elem_id}] selector='{target_el.selector}'"
                            return loc, ResolutionStrategy.SNAPSHOT_ID, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.SNAPSHOT_ID, confidence=0.98)
                    except Exception:
                        pass

                # Try role + name from snapshot element
                if target_el.role and target_el.name:
                    try:
                        loc = page.get_by_role(target_el.role, name=target_el.name).first
                        if loc.count() > 0:
                            desc = f"snapshot_role='{target_el.role}' name='{target_el.name}'"
                            return loc, ResolutionStrategy.ACCESSIBILITY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.ACCESSIBILITY, confidence=0.95)
                    except Exception:
                        pass

                # Try text + tag locator
                if target_el.text and target_el.tag:
                    try:
                        loc = page.locator(target_el.tag).filter(has_text=target_el.text).first
                        if loc.count() > 0:
                            desc = f"tag='{target_el.tag}' text='{target_el.text}'"
                            return loc, ResolutionStrategy.DOM_HIERARCHY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.DOM_HIERARCHY, confidence=0.90)
                    except Exception:
                        pass

                # Visual bounding box center from snapshot
                bbox = target_el.bounding_box
                if bbox and bbox.width > 0 and bbox.height > 0:
                    center_x = bbox.x + (bbox.width / 2.0)
                    center_y = bbox.y + (bbox.height / 2.0)
                    desc = f"snapshot_bbox=({center_x}, {center_y})"
                    return None, ResolutionStrategy.VISUAL_ANALYSIS, desc, (center_x, center_y), TargetConfidence(target=desc, method=ResolutionStrategy.VISUAL_ANALYSIS, confidence=0.85)

        # 2. Strategy 2: Accessibility Role & Accessible Name
        if role and name:
            try:
                loc = page.get_by_role(role, name=name).first
                if loc.count() > 0:
                    desc = f"role='{role}' name='{name}'"
                    return loc, ResolutionStrategy.ACCESSIBILITY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.ACCESSIBILITY, confidence=0.95)
            except Exception:
                pass

        if name:
            try:
                loc = page.get_by_label(name).first
                if loc.count() > 0:
                    desc = f"accessible_label='{name}'"
                    return loc, ResolutionStrategy.ACCESSIBILITY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.ACCESSIBILITY, confidence=0.92)
            except Exception:
                pass

        # 3. Strategy 3: Stable DOM Attributes (data-testid, id, name, aria-label)
        if selector and any(attr in selector for attr in ("data-testid", "data-test-id", "data-cy", "[name=", "#", "aria-label")):
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    desc = f"stable_selector='{selector}'"
                    return loc, ResolutionStrategy.STABLE_ATTRIBUTES, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.STABLE_ATTRIBUTES, confidence=0.90)
            except Exception:
                pass

        # 4. Strategy 4: Visible Text (Exact, then Substring)
        if text:
            clean_text = text.strip()
            try:
                loc = page.get_by_text(clean_text, exact=True).first
                if loc.count() > 0:
                    desc = f"exact_text='{clean_text}'"
                    return loc, ResolutionStrategy.VISIBLE_TEXT, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.VISIBLE_TEXT, confidence=0.88)
                
                loc_fuzzy = page.get_by_text(clean_text, exact=False).first
                if loc_fuzzy.count() > 0:
                    desc = f"text='{clean_text}'"
                    return loc_fuzzy, ResolutionStrategy.VISIBLE_TEXT, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.VISIBLE_TEXT, confidence=0.82)
            except Exception:
                pass

        # 5. Strategy 5: DOM Hierarchy & Context
        if selector:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    desc = f"selector='{selector}'"
                    return loc, ResolutionStrategy.DOM_HIERARCHY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.DOM_HIERARCHY, confidence=0.75)
            except Exception:
                pass

        # 6. Strategy 6: Coordinates (Fallback only)
        if coordinates:
            desc = f"coords=({coordinates[0]}, {coordinates[1]})"
            return None, ResolutionStrategy.COORDINATES, desc, coordinates, TargetConfidence(target=desc, method=ResolutionStrategy.COORDINATES, confidence=0.50)

        desc = "Unknown target"
        return None, ResolutionStrategy.ACCESSIBILITY, desc, None, TargetConfidence(target=desc, method=ResolutionStrategy.ACCESSIBILITY, confidence=0.0)

target_resolver = TargetResolver()

