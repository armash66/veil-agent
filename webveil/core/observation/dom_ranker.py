"""
Deterministic Rule-Based DOM Pruner.
Compresses raw DOM trees down to essential interactive, semantic, and textual elements
using deterministic rule-based filtering (no ML, no fuzzy scoring weights).
"""

import logging
from typing import List, Tuple
from webveil.core.models.schema import DOMNode, TaskRepresentation, DOMRankingMetrics

logger = logging.getLogger("WebVeilDOMPruner")


class DOMRanker:
    """
    On-device deterministic DOM pruner.
    Filters out non-visible nodes, non-interactive empty containers,
    and preserves interactive elements, inputs, forms, and semantic headings.
    """

    def __init__(self, target_top_k: int = 100):
        self.target_top_k = target_top_k

    def rank_and_compress(
        self,
        nodes: List[DOMNode],
        task: TaskRepresentation,
    ) -> Tuple[List[DOMNode], DOMRankingMetrics]:
        """
        Prune DOM nodes using deterministic filtering rules.
        """
        if not nodes:
            return [], DOMRankingMetrics()

        raw_count = len(nodes)

        # Rule 1: Always keep interactive elements and form inputs
        # Rule 2: Keep semantic headings, labels, and links
        # Rule 3: Keep non-empty visible text blocks
        # Rule 4: Drop invisible nodes and empty non-interactive wrappers
        retained: List[DOMNode] = []

        for node in nodes:
            # Drop invisible nodes
            if not getattr(node, "is_visible", True):
                continue

            tag = (node.tag_name or "").lower()
            text = (node.text_content or "").strip()
            is_interactive = getattr(node, "is_interactive", False)
            elem_type = (node.element_type or "").lower()

            # Keep interactive elements (inputs, buttons, selects, textareas, links, interactive role)
            if is_interactive or tag in ["input", "button", "select", "textarea", "a"] or elem_type in ["password", "email", "submit", "text", "search"]:
                retained.append(node)
                continue

            # Keep structural headings, forms, and labels
            if tag in ["h1", "h2", "h3", "h4", "form", "label"]:
                retained.append(node)
                continue

            # Keep text blocks with meaningful text (> 3 chars)
            if text and len(text) > 3:
                retained.append(node)
                continue

        # If retained exceeds target_top_k, prioritize interactive/form elements deterministically
        if len(retained) > self.target_top_k:
            interactive_nodes = [n for n in retained if getattr(n, "is_interactive", False) or n.tag_name in ["input", "button", "select", "textarea", "a"]]
            other_nodes = [n for n in retained if n not in interactive_nodes]
            
            # Reassemble up to target_top_k maintaining original DOM sequence
            needed_other = max(0, self.target_top_k - len(interactive_nodes))
            selected = interactive_nodes + other_nodes[:needed_other]
            selected.sort(key=lambda n: n.node_id)
            retained = selected

        filtered_count = len(retained)
        compression_ratio = ((raw_count - filtered_count) / max(1, raw_count)) * 100.0
        # Estimate ~18 tokens saved per pruned DOM node line
        tokens_saved = int((raw_count - filtered_count) * 18)

        metrics = DOMRankingMetrics(
            raw_nodes=raw_count,
            filtered_nodes=filtered_count,
            compression_ratio=round(compression_ratio, 1),
            estimated_tokens_saved=tokens_saved,
        )

        logger.info(
            f"[DOMPruner] Deterministically pruned {raw_count} → {filtered_count} nodes "
            f"({metrics.compression_ratio}% reduction, ~{tokens_saved} tokens saved)"
        )
        return retained, metrics

