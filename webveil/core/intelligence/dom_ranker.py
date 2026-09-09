"""
Task-Aware DOM Ranker.
Scores DOM nodes using multi-feature extraction:
task relevance, interactivity, visibility, and spatial viewport position.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
from webveil.core.models.schema import DOMNode, TaskRepresentation, DOMRankingMetrics

logger = logging.getLogger("WebVeilIntelligence.Ranker")


class TaskAwareDOMRanker:
    """
    Ranks DOM nodes by combining task-semantic alignment, interactivity,
    visibility heuristics, and spatial priority.
    """

    def __init__(self, target_top_k: int = 100):
        self.target_top_k = target_top_k

    def compute_node_features(self, node: DOMNode, task: Optional[TaskRepresentation]) -> Dict[str, float]:
        """
        Extract numerical features for a DOM node relative to the task.
        """
        features = {
            "task_relevance": 0.0,
            "interactivity": 0.0,
            "visibility": 0.0,
            "position_priority": 0.0,
        }

        # 1. Visibility Feature
        if getattr(node, "is_visible", True):
            features["visibility"] = 0.8
            bbox = node.bounding_box
            if bbox and bbox.get("width", 0) > 0 and bbox.get("height", 0) > 0:
                features["visibility"] = 1.0
        else:
            return features  # Hidden nodes have 0 score

        # 2. Interactivity Feature
        tag = (node.tag_name or "").lower()
        elem_type = (node.element_type or "").lower()
        is_interactive = getattr(node, "is_interactive", False)

        if is_interactive or tag in ["input", "button", "select", "textarea", "a"]:
            features["interactivity"] = 1.0
        elif tag in ["h1", "h2", "h3", "h4", "form", "label"]:
            features["interactivity"] = 0.6
        elif node.text_content and len(node.text_content.strip()) > 3:
            features["interactivity"] = 0.3

        # 3. Task Relevance Feature
        if task:
            text_corpus = f"{node.text_content} {node.name} {node.element_id} {node.attributes.get('placeholder', '')} {node.attributes.get('aria_role', '')} {node.attributes.get('visual_ocr_text', '')}".lower()

            relevance_hits = 0
            # Entity matching
            for entity in task.entities:
                if entity.lower() in text_corpus:
                    relevance_hits += 2

            # Intent keywords
            intent_words = task.intent.lower().replace("_", " ").split()
            for iw in intent_words:
                if iw in text_corpus:
                    relevance_hits += 1

            # Objective / constraints
            if task.objective and task.objective.lower() in text_corpus:
                relevance_hits += 1
            for ck, cv in task.constraints.items():
                if str(cv).lower() in text_corpus or ck.lower() in text_corpus:
                    relevance_hits += 1

            features["task_relevance"] = min(1.0, relevance_hits * 0.3)

        # 4. Position Priority Feature
        bbox = node.bounding_box
        if bbox:
            y = bbox.get("y", 0)
            if y < 800:
                features["position_priority"] = 1.0  # Above fold
            elif y < 1600:
                features["position_priority"] = 0.6
            else:
                features["position_priority"] = 0.3
        else:
            features["position_priority"] = 0.5

        return features

    def score_node(self, node: DOMNode, task: Optional[TaskRepresentation]) -> float:
        """
        Compute weighted composite score S in [0.0, 1.0].
        Weights: Task Relevance (0.40) + Interactivity (0.35) + Visibility (0.15) + Position (0.10).
        """
        f = self.compute_node_features(node, task)
        if f["visibility"] == 0.0:
            return 0.0

        score = (
            0.40 * f["task_relevance"] +
            0.35 * f["interactivity"] +
            0.15 * f["visibility"] +
            0.10 * f["position_priority"]
        )
        return round(score, 4)

    def rank_and_compress(
        self,
        nodes: List[DOMNode],
        task: Optional[TaskRepresentation],
    ) -> Tuple[List[DOMNode], DOMRankingMetrics]:
        """
        Score, filter, and compress DOM nodes down to top-K highest-utility nodes.
        Preserves original document order among retained nodes.
        """
        if not nodes:
            return [], DOMRankingMetrics()

        raw_count = len(nodes)

        # Score all nodes
        scored_nodes = []
        for n in nodes:
            s = self.score_node(n, task)
            if s > 0.05:  # Filter out invisible or purely empty container nodes
                scored_nodes.append((s, n))

        # Sort by score descending to find top-K
        scored_nodes.sort(key=lambda item: item[0], reverse=True)
        top_k_items = scored_nodes[:self.target_top_k]

        # Re-sort top-K by node_id to preserve DOM reading order
        retained = [item[1] for item in top_k_items]
        retained.sort(key=lambda n: n.node_id)

        filtered_count = len(retained)
        compression_ratio = ((raw_count - filtered_count) / max(1, raw_count)) * 100.0
        tokens_saved = int((raw_count - filtered_count) * 18)

        metrics = DOMRankingMetrics(
            raw_nodes=raw_count,
            filtered_nodes=filtered_count,
            compression_ratio=round(compression_ratio, 1),
            estimated_tokens_saved=tokens_saved,
        )

        logger.info(
            f"[TaskAwareDOMRanker] Ranked & compressed {raw_count} → {filtered_count} nodes "
            f"({metrics.compression_ratio}% reduction, ~{tokens_saved} tokens saved)"
        )
        return retained, metrics
