"""
Accessibility tree extraction and semantic structure representation.
Extracts ARIA tree snapshots, classifies semantic roles, and builds compact token-efficient summaries.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("WebVeilPerception.Accessibility")

INTERACTIVE_ROLES = {
    "button", "link", "textbox", "searchbox", "combobox", "checkbox",
    "radio", "switch", "slider", "menuitem", "tab", "option"
}

LANDMARK_ROLES = {
    "banner", "main", "navigation", "complementary", "contentinfo", "search", "region", "form"
}


class AccessibilityExtractor:
    """
    Extracts semantic accessibility tree and metadata from Playwright page.
    Supplements DOM information with screen-reader and assistive hierarchy.
    """

    def extract(self, page) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Extract accessibility tree and concise summary string.
        Returns: (raw_tree_dict, summary_string)
        """
        if not page:
            return None, ""

        try:
            tree = None
            if hasattr(page, "accessibility") and page.accessibility:
                tree = page.accessibility.snapshot(interesting_only=True)

            if not tree:
                # Fallback ARIA evaluator
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

            summary = self.tree_to_summary(tree, depth=0)
            return tree, summary

        except Exception as e:
            logger.warning(f"[A11y] Tree extraction failed: {e}")
            return None, ""

    def tree_to_summary(self, node: Dict[str, Any], depth: int = 0, max_depth: int = 5) -> str:
        """
        Recursively formats an accessibility node tree into a token-efficient indentation string.
        """
        if not node or depth > max_depth:
            return ""

        indent = "  " * depth
        role = node.get("role", "node")
        name = node.get("name", "").strip()
        value = node.get("value", "")

        parts = [f"{indent}[{role}]"]
        if name:
            # Truncate very long labels to conserve tokens
            clean_name = name.replace("\n", " ").strip()
            if len(clean_name) > 60:
                clean_name = clean_name[:57] + "..."
            parts.append(f'"{clean_name}"')
        if value:
            parts.append(f"value={value}")

        lines = [" ".join(parts)]

        for child in node.get("children", []):
            child_summary = self.tree_to_summary(child, depth + 1, max_depth)
            if child_summary:
                lines.append(child_summary)

        return "\n".join(lines)

    def flatten_interactive_nodes(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract flat list of interactive elements from accessibility tree for spatial fusion.
        """
        items = []
        if not node:
            return items

        role = (node.get("role") or "").lower()
        if role in INTERACTIVE_ROLES:
            items.append({
                "role": role,
                "name": node.get("name", "").strip(),
                "value": node.get("value", ""),
                "description": node.get("description", ""),
            })

        for child in node.get("children", []):
            items.extend(self.flatten_interactive_nodes(child))

        return items
