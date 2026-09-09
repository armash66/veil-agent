"""
Local Model & Policy Adapter.
Executes lightweight local model policy predictions for browser actions
with near-zero latency and zero token egress.
"""

import time
import logging
from typing import List, Optional

from webveil.core.models.schema import (
    ActionPlan, BrowserAction, ActionType, ActionResult,
    SanitizedWorldModel, TokenUsage
)
from webveil.core.nlp.task_analyzer import TaskAnalyzer
from webveil.core.intelligence.action_predictor import ActionPredictor

logger = logging.getLogger("WebVeilModels.Adapter")


class LocalModelAdapter:
    """
    On-device specialized action policy adapter.
    Resolves straightforward and unambiguous browser actions locally
    without sending data or incurring remote API latency.
    """

    def __init__(self, model_name: str = "webveil-local-policy-v1", confidence_threshold: float = 0.75):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.task_analyzer = TaskAnalyzer()
        self.predictor = ActionPredictor()
        self.token_usage = TokenUsage()
        self.total_predictions = 0
        self.confident_predictions = 0

    def predict_plan(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> Optional[ActionPlan]:
        """
        Attempt to propose a complete ActionPlan locally.
        Returns ActionPlan if local policy is highly confident, else None.
        """
        t0 = time.time()
        self.total_predictions += 1

        # If previous action had an error, delegate to remote planner for recovery
        if error_context:
            return None

        # Analyze task locally
        task_rep = self.task_analyzer.analyze_task(task)

        # Predict next action using task-aware predictor
        prediction = self.predictor.predict_next_action(
            task=task_rep,
            visible_nodes=world_model.sanitized_dom,
            url=world_model.url,
            action_count=len(action_history),
        )

        if prediction.confidence < self.confidence_threshold:
            logger.debug(
                f"[LocalAdapter] Confidence {prediction.confidence:.2f} below threshold "
                f"{self.confidence_threshold:.2f} — delegating to remote LLM."
            )
            return None

        # Build concrete ActionPlan
        self.confident_predictions += 1
        actions: List[BrowserAction] = []

        if prediction.predicted_action == ActionType.TYPE:
            # Determine appropriate text to type
            cleaned_query = task
            for prefix in ["find me a", "find me", "search for", "look up", "find", "search"]:
                if cleaned_query.lower().startswith(prefix):
                    cleaned_query = cleaned_query[len(prefix):].strip()
                    break

            text_to_type = cleaned_query if cleaned_query else (" ".join(task_rep.entities) if task_rep.entities else task_rep.raw_prompt)

            actions.append(BrowserAction(
                action=ActionType.TYPE,
                node_id=prediction.candidate_node_id,
                text=text_to_type,
                thought=f"Local policy determined to type query into [{prediction.candidate_node_id}]: {prediction.reasoning}",
            ))

        elif prediction.predicted_action == ActionType.CLICK:
            actions.append(BrowserAction(
                action=ActionType.CLICK,
                node_id=prediction.candidate_node_id,
                thought=f"Local policy determined to click target element [{prediction.candidate_node_id}]: {prediction.reasoning}",
            ))

        elif prediction.predicted_action == ActionType.DONE:
            actions.append(BrowserAction(
                action=ActionType.DONE,
                thought=f"Local policy determined task complete: {prediction.reasoning}",
            ))

        elif prediction.predicted_action == ActionType.WAIT:
            actions.append(BrowserAction(
                action=ActionType.WAIT,
                thought="Local policy determined page state is loading.",
            ))

        latency_ms = (time.time() - t0) * 1000
        logger.info(
            f"[LocalAdapter] Fast local action proposed ({actions[0].action.value} on "
            f"[{actions[0].node_id}]) in {latency_ms:.2f}ms (conf: {prediction.confidence:.2f})"
        )

        return ActionPlan(
            actions=actions,
            thought=f"[Local Policy] {prediction.reasoning} (latency: {latency_ms:.1f}ms)",
        )
