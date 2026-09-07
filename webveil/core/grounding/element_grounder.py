"""
Element Grounding & Action Scoring Engine.
Acts as local authority between LLM action proposal and browser control.
Enforces confidence thresholds:
- >= 0.85: EXECUTE immediately
- 0.60 - 0.84: VERIFY (additional DOM check)
- < 0.60: REPLAN (reject action and request LLM re-plan)
"""

import logging
from typing import List, Optional, Dict, Any
from webveil.core.models.schema import BrowserAction, DOMNode, GroundingResult, ActionType

logger = logging.getLogger("WebVeilGrounder")


class ElementGrounder:
    """
    On-device element grounding & verification engine.
    Calculates match confidence between proposed BrowserAction and target DOMNode.
    """

    def ground_action(
        self,
        action: BrowserAction,
        current_nodes: List[DOMNode],
    ) -> GroundingResult:
        """
        Evaluate proposed action against active DOM nodes and compute grounding confidence score.
        """
        # Global actions without node targets (navigate, scroll, keypress, wait, done)
        if action.action in [ActionType.NAVIGATE, ActionType.SCROLL, ActionType.KEYPRESS, ActionType.WAIT, ActionType.DONE]:
            return GroundingResult(
                action=action,
                selected_node_id=None,
                confidence=1.0,
                threshold_action="EXECUTE",
                reasoning="Global action requires no target node grounding.",
            )

        if action.node_id is None:
            return GroundingResult(
                action=action,
                selected_node_id=None,
                confidence=0.0,
                threshold_action="REPLAN",
                reasoning=f"Action '{action.action.value}' missing target node_id.",
            )

        # Find target node in active DOM
        target_node = next((n for n in current_nodes if n.node_id == action.node_id), None)

        if not target_node:
            return GroundingResult(
                action=action,
                selected_node_id=action.node_id,
                confidence=0.0,
                threshold_action="REPLAN",
                reasoning=f"Target node [{action.node_id}] not found in active DOM observation (stale element).",
            )

        # Compute confidence factors
        confidence = 0.50
        alternatives: List[Dict[str, Any]] = []

        # Factor 1: Visibility & Interactivity check (+0.30)
        if target_node.is_visible and target_node.is_interactive:
            confidence += 0.30
        elif target_node.is_visible:
            confidence += 0.15

        # Factor 2: Tag/Type Compatibility (+0.15)
        if action.action == ActionType.TYPE and target_node.tag_name in ["input", "textarea"]:
            confidence += 0.15
        elif action.action == ActionType.CLICK and target_node.tag_name in ["button", "a", "input"]:
            confidence += 0.15
        elif action.action == ActionType.SELECT and target_node.tag_name in ["select", "option"]:
            confidence += 0.15

        # Factor 3: Thought alignment (+0.05)
        if action.thought:
            confidence += 0.05

        confidence = round(min(1.0, confidence), 2)

        # Find alternative candidate nodes with matching tag/type
        for alt in current_nodes:
            if alt.node_id != target_node.node_id and alt.tag_name == target_node.tag_name and alt.is_interactive:
                alternatives.append({
                    "node_id": alt.node_id,
                    "tag_name": alt.tag_name,
                    "text": alt.text_content[:30],
                })
                if len(alternatives) >= 3:
                    break

        # Threshold decision
        threshold_action = "EXECUTE"
        if confidence < 0.60:
            threshold_action = "REPLAN"
        elif confidence < 0.85:
            threshold_action = "VERIFY"

        result = GroundingResult(
            action=action,
            selected_node_id=target_node.node_id,
            confidence=confidence,
            alternative_nodes=alternatives,
            threshold_action=threshold_action,
            reasoning=f"Node [{target_node.node_id}] <{target_node.tag_name}> grounded with {int(confidence*100)}% confidence.",
        )

        logger.info(
            f"[Grounder] Action '{action.action.value}' -> Node [{target_node.node_id}] | "
            f"Confidence: {confidence} | Decision: {threshold_action}"
        )
        return result
