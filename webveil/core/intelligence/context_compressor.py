"""
Token-Budget-Aware Context Compressor.
Selects and compresses DOM and multimodal observation context
strictly within a target token budget while preserving critical task structures.
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
from webveil.core.models.schema import DOMNode

logger = logging.getLogger("WebVeilIntelligence.Compressor")


@dataclass
class CompressionBudgetReport:
    raw_tokens: int
    compressed_tokens: int
    token_budget: int
    nodes_retained: int
    nodes_dropped: int
    budget_exhausted: bool


class ContextCompressor:
    """
    Enforces token budget limits on observation context by selecting
    highest-utility nodes while maintaining structural coherency.
    """

    def __init__(self, max_token_budget: int = 2500):
        self.max_token_budget = max_token_budget

    @staticmethod
    def estimate_node_tokens(node: DOMNode) -> int:
        """
        Estimate token count of a single DOM node formatted for model context.
        Approx 1 token per 4 characters across tag, attributes, and text.
        """
        raw_repr = (
            f"[{node.node_id}] <{node.tag_name} type='{node.element_type}' "
            f"name='{node.name}' val='{node.value}'>{node.text_content}</{node.tag_name}>"
        )
        return max(4, int(len(raw_repr) / 3.8))

    def compress_to_budget(
        self,
        ranked_nodes: List[DOMNode],
        budget_override: Optional[int] = None,
    ) -> Tuple[List[DOMNode], CompressionBudgetReport]:
        """
        Select nodes that fit within the token budget.
        Nodes should ideally be sorted by priority or utility before calling.
        """
        budget = budget_override or self.max_token_budget
        total_raw_tokens = sum(self.estimate_node_tokens(n) for n in ranked_nodes)

        retained: List[DOMNode] = []
        current_tokens = 0
        budget_exhausted = False

        # Phase 1: Always prioritize interactive elements
        interactive_nodes = [n for n in ranked_nodes if n.is_interactive]
        non_interactive_nodes = [n for n in ranked_nodes if not n.is_interactive]

        for node in interactive_nodes:
            cost = self.estimate_node_tokens(node)
            if current_tokens + cost <= budget:
                retained.append(node)
                current_tokens += cost
            else:
                budget_exhausted = True
                break

        # Phase 2: Fill remaining budget with semantic text/headings
        if not budget_exhausted:
            for node in non_interactive_nodes:
                cost = self.estimate_node_tokens(node)
                if current_tokens + cost <= budget:
                    retained.append(node)
                    current_tokens += cost
                else:
                    budget_exhausted = True
                    break

        # Re-sort retained nodes by node_id to preserve DOM reading order
        retained.sort(key=lambda n: n.node_id)

        report = CompressionBudgetReport(
            raw_tokens=total_raw_tokens,
            compressed_tokens=current_tokens,
            token_budget=budget,
            nodes_retained=len(retained),
            nodes_dropped=len(ranked_nodes) - len(retained),
            budget_exhausted=budget_exhausted,
        )

        logger.info(
            f"[ContextCompressor] Budget: {budget} tokens | "
            f"Used: {current_tokens} tokens ({report.nodes_retained} nodes kept, {report.nodes_dropped} dropped)"
        )
        return retained, report
