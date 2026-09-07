"""
Task-Aware DOM Intelligence & Relevance Ranker.
Compresses raw DOM trees (e.g. 2,700+ nodes on Amazon) down to ~80-120 high-value elements
using a multi-factor hybrid scoring function before remote LLM egress.
"""

import math
import logging
from typing import List, Tuple, Dict, Any
from webveil.core.models.schema import DOMNode, TaskRepresentation, DOMRankingMetrics

logger = logging.getLogger("WebVeilDOMRanker")


class DOMRanker:
    """
    On-device task-aware DOM compression engine.
    Applies multi-factor scoring:
    Score(node) = w1*text_similarity + w2*constraint_match + w3*interactivity + w4*role + w5*structure
    """

    def __init__(
        self,
        w1_sim: float = 0.30,
        w2_constraint: float = 0.25,
        w3_interactive: float = 0.20,
        w4_role: float = 0.15,
        w5_structure: float = 0.10,
        target_top_k: int = 100,
    ):
        self.w1 = w1_sim
        self.w2 = w2_constraint
        self.w3 = w3_interactive
        self.w4 = w4_role
        self.w5 = w5_structure
        self.target_top_k = target_top_k

    def rank_and_compress(
        self,
        nodes: List[DOMNode],
        task: TaskRepresentation,
    ) -> Tuple[List[DOMNode], DOMRankingMetrics]:
        """
        Rank DOM nodes and select top-K relevant elements.
        Always preserves form inputs, primary search boxes, and active submit buttons.
        """
        if not nodes:
            return [], DOMRankingMetrics()

        raw_count = len(nodes)
        
        # If node count is already small (< 60), keep all
        if raw_count <= 60:
            metrics = DOMRankingMetrics(
                raw_nodes=raw_count,
                filtered_nodes=raw_count,
                compression_ratio=0.0,
                estimated_tokens_saved=0,
            )
            return nodes, metrics

        task_words = set(task.raw_prompt.lower().split() + [e.lower() for e in task.entities])
        constraint_words = set(str(v).lower() for v in task.constraints.values())

        scored_nodes: List[Tuple[float, DOMNode]] = []

        for node in nodes:
            score = 0.0

            # Factor 1: Task text similarity (0.0 - 1.0)
            node_text = f"{node.text_content} {node.name} {node.attributes.get('placeholder', '')} {node.attributes.get('aria-label', '')}".lower()
            matching_words = sum(1 for w in task_words if len(w) > 2 and w in node_text)
            sim_score = min(1.0, matching_words / max(1, len(task_words)))
            score += self.w1 * sim_score

            # Factor 2: Constraint match (0.0 - 1.0)
            c_score = 0.0
            if any(cw in node_text for cw in constraint_words if len(cw) > 1):
                c_score = 1.0
            score += self.w2 * c_score

            # Factor 3: Interactivity (0.0 - 1.0)
            int_score = 1.0 if node.is_interactive else 0.2
            score += self.w3 * int_score

            # Factor 4: Semantic role (0.0 - 1.0)
            role_score = 0.3
            if node.tag_name in ["input", "button", "select", "textarea"]:
                role_score = 1.0
            elif node.tag_name in ["a", "h1", "h2", "h3"]:
                role_score = 0.7
            score += self.w4 * role_score

            # Factor 5: Structural relevance (0.0 - 1.0)
            struct_score = 0.5
            if node.bounding_box and node.bounding_box.get("y", 9999) < 1200:
                # Elements near top viewport get structural priority
                struct_score = 0.9
            score += self.w5 * struct_score

            # ALWAYS preserve critical form elements & search bars
            if node.tag_name == "input" and any(k in node_text for k in ["search", "q", "query", "kw", "text"]):
                score += 5.0
            if node.element_type in ["password", "email", "submit"]:
                score += 5.0

            scored_nodes.append((score, node))

        # Sort descending by score
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # Select top-K
        selected_pairs = scored_nodes[:self.target_top_k]
        
        # Sort selected nodes back into original node_id order to preserve DOM sequence
        selected_nodes = [pair[1] for pair in selected_pairs]
        selected_nodes.sort(key=lambda n: n.node_id)

        filtered_count = len(selected_nodes)
        compression_ratio = ((raw_count - filtered_count) / max(1, raw_count)) * 100.0
        # Average ~18 tokens per raw DOM line string
        tokens_saved = int((raw_count - filtered_count) * 18)

        metrics = DOMRankingMetrics(
            raw_nodes=raw_count,
            filtered_nodes=filtered_count,
            compression_ratio=round(compression_ratio, 1),
            estimated_tokens_saved=tokens_saved,
        )

        logger.info(
            f"[DOMRanker] Compressed {raw_count} → {filtered_count} nodes "
            f"({metrics.compression_ratio}% reduction, ~{tokens_saved} tokens saved)"
        )
        return selected_nodes, metrics
