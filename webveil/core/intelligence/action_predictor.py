"""
Local Action Predictor and Intent Matcher.
Predicts the most probable next browser action type and candidate target element
from local task understanding and observed page state.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from webveil.core.models.schema import DOMNode, ActionType, TaskRepresentation

logger = logging.getLogger("WebVeilIntelligence.Predictor")


@dataclass
class ActionPrediction:
    predicted_action: ActionType
    candidate_node_id: Optional[int]
    confidence: float
    reasoning: str


class ActionPredictor:
    """
    Predicts likely next browser actions to guide remote reasoning,
    constrain exploration search space, and provide high-confidence local shortcuts.
    """

    def predict_next_action(
        self,
        task: TaskRepresentation,
        visible_nodes: List[DOMNode],
        url: str = "",
        action_count: int = 0,
    ) -> ActionPrediction:
        """
        Predict probable next action based on task intent and current page elements.
        """
        if not visible_nodes:
            return ActionPrediction(
                predicted_action=ActionType.WAIT,
                candidate_node_id=None,
                confidence=0.3,
                reasoning="No visible DOM elements observed on page.",
            )

        intent = (task.intent or "").lower()

        # 1. Search Intent: Look for search input field if we haven't typed yet
        if intent in ["product_search", "information_retrieval"]:
            for node in visible_nodes:
                tag = (node.tag_name or "").lower()
                elem_type = (node.element_type or "").lower()
                name_field = f"{node.name} {node.element_id} {node.attributes.get('placeholder', '')}".lower()

                if tag == "input" and (elem_type in ["search", "text"] or "search" in name_field or "find" in name_field):
                    if not node.value or len(node.value.strip()) == 0:
                        return ActionPrediction(
                            predicted_action=ActionType.TYPE,
                            candidate_node_id=node.node_id,
                            confidence=0.92,
                            reasoning=f"Found search input field [{node.node_id}] for intent '{intent}'.",
                        )

            # If search input already filled or submit button present
            for node in visible_nodes:
                tag = (node.tag_name or "").lower()
                text = (node.text_content or "").lower()
                name_field = f"{node.name} {node.element_id} {node.attributes.get('aria_role', '')}".lower()
                if (tag in ["button", "input"] and any(w in text or w in name_field for w in ["search", "find", "submit", "go"])):
                    return ActionPrediction(
                        predicted_action=ActionType.CLICK,
                        candidate_node_id=node.node_id,
                        confidence=0.85,
                        reasoning=f"Found search/submit trigger [{node.node_id}].",
                    )

        # 2. Form Fill Intent
        if intent == "form_fill":
            for node in visible_nodes:
                if (node.tag_name or "").lower() in ["input", "textarea", "select"] and not node.value:
                    return ActionPrediction(
                        predicted_action=ActionType.TYPE,
                        candidate_node_id=node.node_id,
                        confidence=0.88,
                        reasoning=f"Found empty form input field [{node.node_id}].",
                    )

        # 3. Navigation / Confirmation check
        if action_count > 5:
            # If several actions executed and page displays success/confirmation
            for node in visible_nodes:
                text = (node.text_content or "").lower()
                if any(w in text for w in ["thank you", "confirmed", "order placed", "success", "results for"]):
                    return ActionPrediction(
                        predicted_action=ActionType.DONE,
                        candidate_node_id=None,
                        confidence=0.75,
                        reasoning="Observed confirmation or result indicator on page.",
                    )

        # Fallback default: Click highest interactive element or wait
        interactive = [n for n in visible_nodes if n.is_interactive]
        if interactive:
            return ActionPrediction(
                predicted_action=ActionType.CLICK,
                candidate_node_id=interactive[0].node_id,
                confidence=0.50,
                reasoning=f"Defaulting to primary interactive element [{interactive[0].node_id}].",
            )

        return ActionPrediction(
            predicted_action=ActionType.WAIT,
            candidate_node_id=None,
            confidence=0.40,
            reasoning="Awaiting further page load or state transition.",
        )
