"""Browser Snapshot Engine: DOM & Accessibility Tree Parser for token-optimized LLM consumption."""
import re
from typing import Any, Dict, List, Optional
from browser.schema import InteractiveElement, PageSnapshot
from browser.security_manager import security_manager

MAX_SNAPSHOT_TEXT_CHARS = 3500
MAX_INTERACTIVE_ELEMENTS = 40

JS_ACCESSIBILITY_EXTRACTOR = """
(() => {
  const interactiveTags = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'];
  const elements = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;

  let index = 1;
  while (node && index <= 50) {
    const tag = node.tagName;
    const isInteractive = interactiveTags.includes(tag) || 
                          node.getAttribute('role') === 'button' || 
                          node.getAttribute('role') === 'link' ||
                          node.onclick != null ||
                          node.getAttribute('tabindex') === '0';

    const rect = node.getBoundingClientRect();
    const isVisible = rect.width > 0 && rect.height > 0 && 
                      window.getComputedStyle(node).visibility !== 'hidden' && 
                      window.getComputedStyle(node).display !== 'none';

    if (isInteractive && isVisible) {
      let text = (node.innerText || node.getAttribute('aria-label') || node.getAttribute('title') || node.getAttribute('placeholder') || node.value || '').trim();
      text = text.replace(/\\s+/g, ' ').slice(0, 80);

      // Generate robust selector
      let selector = tag.toLowerCase();
      if (node.id) {
        selector = `#${node.id}`;
      } else if (node.getAttribute('name')) {
        selector = `${tag.toLowerCase()}[name="${node.getAttribute('name')}"]`;
      } else if (node.getAttribute('aria-label')) {
        selector = `${tag.toLowerCase()}[aria-label="${node.getAttribute('aria-label')}"]`;
      } else if (node.className && typeof node.className === 'string' && node.className.trim()) {
        const firstClass = node.className.trim().split(/\\s+/)[0];
        if (firstClass && !firstClass.includes(':')) {
          selector = `${tag.toLowerCase()}.${firstClass}`;
        }
      }

      elements.push({
        id: index,
        tag: tag.toLowerCase(),
        role: node.getAttribute('role') || undefined,
        text: text || (tag === 'INPUT' ? 'input field' : 'interactive element'),
        selector: selector,
        placeholder: node.getAttribute('placeholder') || undefined,
        value: (tag === 'INPUT' && node.type !== 'password') ? node.value : undefined,
        input_type: node.getAttribute('type') || undefined,
        is_clickable: ['BUTTON', 'A'].includes(tag) || node.getAttribute('role') === 'button',
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
                interactive_elements.append(InteractiveElement(
                    id=item.get("id", len(interactive_elements) + 1),
                    tag=item.get("tag", "div"),
                    role=item.get("role"),
                    text=item.get("text", ""),
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
            kind = el.tag
            if el.is_input:
                kind = f"input[{el.input_type or 'text'}]"
                desc = f'placeholder="{el.placeholder}"' if el.placeholder else f'value="{el.value or ""}"'
                element_lines.append(f"[{el.id}] {kind} {desc} (selector: `{el.selector}`)")
            else:
                element_lines.append(f"[{el.id}] {kind} \"{el.text}\" (selector: `{el.selector}`)")

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
