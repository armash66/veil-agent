"""
Accessibility Tree Observer.
Extracts semantic page structure via Playwright's accessibility API.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("WebVeilA11y")


class A11yObserver:
    """
    Extracts the accessibility tree from a Playwright page.
    Provides semantic roles, names, and states that DOM extraction may miss.
    """

    def extract(self, page) -> tuple[Optional[Dict[str, Any]], str]:
        """
        Returns (raw_tree, summary_string).
        The summary is a token-efficient text representation for LLM context.
        """
        if not page:
            return None, ""

        try:
            # Try modern Playwright accessibility snapshot
            if hasattr(page, 'accessibility') and page.accessibility:
                tree = page.accessibility.snapshot(interesting_only=True)
            else:
                # Fallback: extract ARIA info via JS evaluation
                tree = page.evaluate("""() => {
                    function buildTree(el, depth) {
                        if (depth > 5) return null;
                        const role = el.getAttribute('role') || el.tagName.toLowerCase();
                        const name = el.getAttribute('aria-label') || el.title || el.innerText?.slice(0, 50) || '';
                        const children = [];
                        for (const child of el.children) {
                            const ct = buildTree(child, depth + 1);
                            if (ct) children.push(ct);
                        }
                        if (!name && children.length === 0 && !['input','button','a','select','textarea'].includes(el.tagName.toLowerCase())) return null;
                        return { role, name: name.trim(), children };
                    }
                    return buildTree(document.body, 0);
                }""")

            if not tree:
                return None, ""

            summary = self._tree_to_summary(tree, depth=0)
            return tree, summary

        except Exception as e:
            logger.warning(f"[A11y] Accessibility tree extraction failed: {e}")
            return None, ""

    def _tree_to_summary(self, node: Dict[str, Any], depth: int) -> str:
        """
        Recursively converts the accessibility tree into a compact text summary.
        Format: role "name" [state] (indented by depth)
        """
        lines = []
        indent = "  " * depth

        role = node.get("role", "")
        name = node.get("name", "")
        value = node.get("value", "")

        # Build compact descriptor
        parts = []
        if role:
            parts.append(role)
        if name:
            parts.append(f'"{name}"')
        if value:
            parts.append(f'value="{value}"')

        # Add state flags
        for flag in ["checked", "disabled", "expanded", "selected", "required", "focused"]:
            if node.get(flag):
                parts.append(f"[{flag}]")

        if parts:
            lines.append(f"{indent}{' '.join(parts)}")

        # Recurse into children
        children = node.get("children", [])
        for child in children:
            lines.append(self._tree_to_summary(child, depth + 1))

        return "\n".join(lines)
