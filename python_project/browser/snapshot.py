"""Browser Snapshot Engine: DOM & Accessibility Tree Parser for token-optimized LLM consumption."""
import re
from typing import Any, Dict, List, Optional
from browser.schema import InteractiveElement, PageSnapshot, BoundingBox
from browser.security_manager import security_manager

MAX_SNAPSHOT_TEXT_CHARS = 4000
MAX_INTERACTIVE_ELEMENTS = 50

JS_ACCESSIBILITY_EXTRACTOR = """
(() => {
  const interactiveTags = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'];
  const elements = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;

  let index = 1;
  while (node && index <= 60) {
    const tag = node.tagName;
    const roleAttr = node.getAttribute('role');
    const isInteractive = interactiveTags.includes(tag) || 
                          roleAttr === 'button' || 
                          roleAttr === 'link' ||
                          roleAttr === 'checkbox' ||
                          roleAttr === 'tab' ||
                          roleAttr === 'menuitem' ||
                          node.onclick != null ||
                          node.getAttribute('tabindex') === '0';

    const rect = node.getBoundingClientRect();
    const isVisible = rect.width > 0 && rect.height > 0 && 
                      window.getComputedStyle(node).visibility !== 'hidden' && 
                      window.getComputedStyle(node).display !== 'none';

    if (isInteractive && isVisible) {
      let accessibleName = (node.getAttribute('aria-label') || node.getAttribute('title') || node.getAttribute('placeholder') || node.innerText || node.value || '').trim();
      accessibleName = accessibleName.replace(/\\s+/g, ' ').slice(0, 100);

      // Extract stable attributes
      const stableAttrs = {};
      if (node.id) stableAttrs['id'] = node.id;
      if (node.getAttribute('name')) stableAttrs['name'] = node.getAttribute('name');
      if (node.getAttribute('data-testid')) stableAttrs['data-testid'] = node.getAttribute('data-testid');
      if (node.getAttribute('data-test-id')) stableAttrs['data-test-id'] = node.getAttribute('data-test-id');
      if (node.getAttribute('data-cy')) stableAttrs['data-cy'] = node.getAttribute('data-cy');
      if (node.getAttribute('aria-label')) stableAttrs['aria-label'] = node.getAttribute('aria-label');

      // Extract ARIA attributes
      const ariaAttrs = {};
      for (let i = 0; i < node.attributes.length; i++) {
        const attr = node.attributes[i];
        if (attr.name.startsWith('aria-')) {
          ariaAttrs[attr.name] = attr.value;
        }
      }

      // Generate robust selector
      let selector = tag.toLowerCase();
      if (node.id) {
        selector = `#${node.id}`;
      } else if (node.getAttribute('data-testid')) {
        selector = `[data-testid="${node.getAttribute('data-testid')}"]`;
      } else if (node.getAttribute('name')) {
        selector = `${tag.toLowerCase()}[name="${node.getAttribute('name')}"]`;
      } else if (node.getAttribute('aria-label')) {
        selector = `${tag.toLowerCase()}[aria-label="${node.getAttribute('aria-label')}"]`;
      } else if (node.className && typeof node.className === 'string' && node.className.trim()) {
        const firstClass = node.className.trim().split(/\\s+/)[0];
        if (firstClass && !firstClass.includes(':') && !firstClass.includes('/')) {
          selector = `${tag.toLowerCase()}.${firstClass}`;
        }
      }

      // Parent context
      let parentContext = undefined;
      if (node.parentElement) {
        const pTag = node.parentElement.tagName.toLowerCase();
        const pRole = node.parentElement.getAttribute('role');
        const pAria = node.parentElement.getAttribute('aria-label');
        if (pAria) parentContext = `${pTag}[aria-label="${pAria}"]`;
        else if (pRole) parentContext = `${pTag}[role="${pRole}"]`;
        else parentContext = pTag;
      }

      // Role determination
      const computedRole = roleAttr || (tag === 'A' ? 'link' : tag === 'BUTTON' ? 'button' : tag === 'INPUT' ? (node.type === 'checkbox' ? 'checkbox' : 'textbox') : 'generic');

      elements.push({
        id: index,
        element_id: `e${index}`,
        tag: tag.toLowerCase(),
        role: computedRole,
        name: accessibleName,
        text: (node.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
        href: node.getAttribute('href') || undefined,
        aria_attributes: ariaAttrs,
        stable_attributes: stableAttrs,
        visible: true,
        enabled: !node.disabled,
        bounding_box: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        },
        parent_context: parentContext,
        selector: selector,
        placeholder: node.getAttribute('placeholder') || undefined,
        value: (tag === 'INPUT' && node.type !== 'password') ? node.value : undefined,
        input_type: node.getAttribute('type') || undefined,
        is_clickable: ['BUTTON', 'A'].includes(tag) || ['button', 'link', 'tab'].includes(computedRole),
        is_input: ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)
      });
      index++;
    }
    node = walker.nextNode();
  }
  return elements;
})()
"""

class SnapshotParser:
    """Parses raw HTML / Playwright page DOM into structured, LLM-ready snapshots."""

    @staticmethod
    def build_snapshot(
        title: str,
        url: str,
        active_tab_id: str,
        elements_data: List[Dict[str, Any]],
        visible_text: str
    ) -> PageSnapshot:
        """Construct structured PageSnapshot instance with token-optimized formatted string."""
        interactive_elements: List[InteractiveElement] = []
        for item in elements_data[:MAX_INTERACTIVE_ELEMENTS]:
            try:
                bbox_data = item.get("bounding_box")
                bbox = BoundingBox(**bbox_data) if bbox_data else None

                idx = item.get("id", len(interactive_elements) + 1)
                elem_id = item.get("element_id") or f"e{idx}"

                interactive_elements.append(InteractiveElement(
                    id=idx,
                    element_id=elem_id,
                    tag=item.get("tag", "div"),
                    role=item.get("role"),
                    name=item.get("name", ""),
                    text=item.get("text", "") or item.get("name", ""),
                    href=item.get("href"),
                    aria_attributes=item.get("aria_attributes", {}),
                    stable_attributes=item.get("stable_attributes", {}),
                    visible=item.get("visible", True),
                    enabled=item.get("enabled", True),
                    bounding_box=bbox,
                    parent_context=item.get("parent_context"),
                    selector=item.get("selector", "body"),
                    placeholder=item.get("placeholder"),
                    value=item.get("value"),
                    input_type=item.get("input_type"),
                    is_clickable=item.get("is_clickable", True),
                    is_input=item.get("is_input", False)
                ))
            except Exception:
                continue

        # Clean and sanitize visible text
        cleaned_text = re.sub(r'\s+', ' ', visible_text).strip()[:MAX_SNAPSHOT_TEXT_CHARS]
        sanitized_text = security_manager.sanitize_page_text(cleaned_text)

        # Build formatted representation for LLM
        element_lines = []
        for el in interactive_elements:
            role_desc = f'role="{el.role}"' if el.role else el.tag
            label_desc = f'"{el.name or el.text}"' if (el.name or el.text) else ""
            href_desc = f'href="{el.href}"' if el.href else ""
            bbox_desc = f'bbox:({int(el.bounding_box.x)},{int(el.bounding_box.y)},{int(el.bounding_box.width)}x{int(el.bounding_box.height)})' if el.bounding_box else ""
            
            extras = " ".join(filter(None, [label_desc, href_desc, bbox_desc]))
            if el.is_input:
                inp_desc = f'placeholder="{el.placeholder}"' if el.placeholder else f'value="{el.value or ""}"'
                element_lines.append(f"[{el.id} / {el.element_id}] input[{el.input_type or 'text'}] {inp_desc} (selector: `{el.selector}`)")
            else:
                element_lines.append(f"[{el.id} / {el.element_id}] {role_desc} {extras} (selector: `{el.selector}`)")

        formatted_elements = "\n".join(element_lines) if element_lines else "No interactive elements detected."

        formatted_str = (
            f"Page Title: {title}\n"
            f"URL: {url}\n"
            f"Active Tab ID: {active_tab_id}\n\n"
            f"Interactive Elements:\n"
            f"{formatted_elements}\n\n"
            f"Page Text Content:\n"
            f"{security_manager.wrap_untrusted_content(sanitized_text, url)}"
        )

        return PageSnapshot(
            title=title,
            url=url,
            active_tab_id=active_tab_id,
            elements=interactive_elements,
            visible_text=sanitized_text,
            formatted_snapshot=formatted_str
        )

snapshot_parser = SnapshotParser()
