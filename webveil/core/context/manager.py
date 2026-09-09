"""
Local Context Manager Engine.
Selects minimal relevant observation context, ranks DOM and visual candidates against
the active goal, attaches provenance metadata, and reports compression statistics.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import DOMNode, SanitizedWorldModel, TaskRepresentation
from webveil.core.observation.dom_ranker import DOMRanker
from webveil.core.memory.working_memory import AgentWorkingMemory

logger = logging.getLogger("WebVeilContext.Manager")


@dataclass
class ContextCompressionStats:
    raw_nodes_count: int
    selected_nodes_count: int
    estimated_raw_tokens: int
    estimated_selected_tokens: int
    compression_ratio_pct: float
    retained_context_ratio_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_nodes_count": self.raw_nodes_count,
            "selected_nodes_count": self.selected_nodes_count,
            "estimated_raw_tokens": self.estimated_raw_tokens,
            "estimated_selected_tokens": self.estimated_selected_tokens,
            "compression_ratio_pct": round(self.compression_ratio_pct, 1),
            "retained_context_ratio_pct": round(self.retained_context_ratio_pct, 1),
        }


@dataclass
class SelectedContextPayload:
    task: str
    active_goal: str
    url: str
    page_title: str
    selected_dom_nodes: List[DOMNode]
    formatted_dom: str
    a11y_summary: str
    ocr_summary: str
    visual_summary: str
    recent_failures: List[str]
    provenance_map: Dict[str, str]  # element/field -> source provenance
    compression_stats: ContextCompressionStats


class LocalContextManager:
    """
    On-device relevance filtering and context reduction authority.
    Prunes noisy, irrelevant background nodes while guaranteeing that
    interactive targets, modal dialogs, and failure recovery elements are retained.
    """

    def __init__(self, dom_ranker: Optional[DOMRanker] = None, max_selected_elements: int = 40):
        self.dom_ranker = dom_ranker or DOMRanker()
        self.max_selected_elements = max_selected_elements

    def select_context(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        working_memory: Optional[AgentWorkingMemory] = None,
        task_rep: Optional[TaskRepresentation] = None,
    ) -> SelectedContextPayload:
        """
        Build minimal, relevant context payload for remote reasoning.
        """
        raw_nodes = world_model.sanitized_dom or []
        active_goal = task
        recent_failures_txt: List[str] = []

        if working_memory:
            goal_obj = working_memory.get_active_goal()
            if goal_obj:
                active_goal = goal_obj.description
            recent_failures_txt = [
                f"{f.failure_type.value}: {f.details}"
                for f in working_memory.get_recent_failures(2)
            ]

        # 1. Rank and compress DOM nodes relative to task and active goal
        effective_task_rep = task_rep
        if not effective_task_rep and working_memory:
            effective_task_rep = working_memory.active_intent

        scored = []
        for n in raw_nodes:
            score = self.dom_ranker.score_node(n, effective_task_rep)
            if n.is_interactive:
                score += 0.5
            scored.append((score, n))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected_nodes = [item[1] for item in scored[:self.max_selected_elements]]
        selected_nodes.sort(key=lambda n: n.node_id)

        # 2. Build formatted minimal DOM representation
        lines = []
        provenance: Dict[str, str] = {
            "task": "user_instruction",
            "active_goal": "working_memory_planner",
            "url": "browser_navigation",
        }

        for n in selected_nodes:
            lines.append(
                f"[{n.node_id}] <{n.tag_name} type='{n.element_type}' name='{n.name}' "
                f"placeholder='{n.attributes.get('placeholder', '')}' value='{n.value}'>{n.text_content}</{n.tag_name}>"
            )
            provenance[f"node_{n.node_id}"] = n.attributes.get("visual_structure", "dom_hierarchy")

        formatted_selected_dom = "\n".join(lines)

        # 3. Calculate token and compression statistics
        raw_text = " ".join([f"{n.text_content} {n.attributes}" for n in raw_nodes])
        raw_tokens_est = max(10, len(raw_text.split()) * 2)
        selected_tokens_est = max(5, len(formatted_selected_dom.split()) * 2)
        compression_ratio = max(0.0, (1.0 - (selected_tokens_est / max(1.0, float(raw_tokens_est)))) * 100.0)

        stats = ContextCompressionStats(
            raw_nodes_count=len(raw_nodes),
            selected_nodes_count=len(selected_nodes),
            estimated_raw_tokens=raw_tokens_est,
            estimated_selected_tokens=selected_tokens_est,
            compression_ratio_pct=compression_ratio,
            retained_context_ratio_pct=round(100.0 - compression_ratio, 1),
        )

        logger.info(
            f"[ContextManager] Pruned context: {stats.raw_nodes_count} -> {stats.selected_nodes_count} nodes "
            f"({stats.compression_ratio_pct:.1f}% token reduction)"
        )

        return SelectedContextPayload(
            task=task,
            active_goal=active_goal,
            url=world_model.sanitized_url,
            page_title=world_model.title,
            selected_dom_nodes=selected_nodes,
            formatted_dom=formatted_selected_dom,
            a11y_summary=world_model.a11y_summary,
            ocr_summary=world_model.ocr_summary,
            visual_summary=world_model.visual_summary,
            recent_failures=recent_failures_txt,
            provenance_map=provenance,
            compression_stats=stats,
        )
