"""
Hybrid Reasoning Router.
Intelligently routes browser-agent decision steps between zero-latency local policies
and full remote reasoning models (Gemini) based on task ambiguity and confidence.
"""

import logging
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import (
    ActionPlan, ActionResult, SanitizedWorldModel, TokenUsage
)
from webveil.reasoning.provider import ReasoningProvider
from webveil.models.adapter import LocalModelAdapter

logger = logging.getLogger("WebVeilModels.Router")


class HybridReasoningRouter:
    """
    Drop-in ReasoningProvider that routes straightforward browser actions locally
    while preserving remote Gemini reasoning for complex, multi-step, or recovering tasks.
    """

    def __init__(
        self,
        remote_provider: ReasoningProvider,
        local_adapter: Optional[LocalModelAdapter] = None,
        confidence_threshold: float = 0.75,
    ):
        self.remote_provider = remote_provider
        self.local_adapter = local_adapter or LocalModelAdapter(confidence_threshold=confidence_threshold)
        self.provider_name = f"hybrid({self.local_adapter.model_name}+{self.remote_provider.provider_name})"
        self.token_usage = TokenUsage()

        # Routing counters
        self.local_calls: int = 0
        self.remote_calls: int = 0
        self.estimated_tokens_saved: int = 0

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """
        Evaluate local policy first. If confident, return immediately without network egress.
        Otherwise delegate to remote provider.
        """
        # 1. Attempt fast local policy inference
        local_plan = self.local_adapter.predict_plan(
            task=task,
            world_model=world_model,
            action_history=action_history,
            error_context=error_context,
        )

        if local_plan is not None:
            self.local_calls += 1
            # Estimate ~350 input tokens and ~80 output tokens saved per local step
            self.estimated_tokens_saved += 430
            logger.info(
                f"[HybridRouter] Route: LOCAL | Local calls: {self.local_calls}, "
                f"Remote calls: {self.remote_calls} (~{self.estimated_tokens_saved} tokens saved)"
            )
            return local_plan

        # 2. Delegate to remote provider
        self.remote_calls += 1
        logger.info(
            f"[HybridRouter] Route: REMOTE ({self.remote_provider.provider_name}) | "
            f"Local calls: {self.local_calls}, Remote calls: {self.remote_calls}"
        )
        plan = self.remote_provider.reason(
            task=task,
            world_model=world_model,
            action_history=action_history,
            error_context=error_context,
        )

        # Synchronize token usage
        if hasattr(self.remote_provider, "token_usage"):
            self.token_usage.input_tokens = self.remote_provider.token_usage.input_tokens
            self.token_usage.output_tokens = self.remote_provider.token_usage.output_tokens
            self.token_usage.total_calls = self.local_calls + self.remote_calls

        return plan

    def reset_token_usage(self):
        """Reset token counters."""
        self.token_usage.reset()
        if hasattr(self.remote_provider, "reset_token_usage"):
            self.remote_provider.reset_token_usage()

    def get_routing_stats(self) -> Dict[str, Any]:
        """Summary of local vs remote routing decisions."""
        total = self.local_calls + self.remote_calls
        local_ratio = round(self.local_calls / max(1, total), 3)
        return {
            "local_calls": self.local_calls,
            "remote_calls": self.remote_calls,
            "total_calls": total,
            "local_ratio": local_ratio,
            "remote_ratio": round(1.0 - local_ratio, 3),
            "estimated_tokens_saved": self.estimated_tokens_saved,
        }
