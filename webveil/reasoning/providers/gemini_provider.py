"""
Gemini Reasoning Provider.
Uses the google-genai SDK with structured JSON output.
"""

import logging
from typing import List, Optional

from webveil.core.models.schema import (
    ActionPlan, ActionResult, SanitizedWorldModel, TokenUsage
)
from webveil.reasoning.provider import (
    SYSTEM_PROMPT, build_reasoning_context, parse_action_plan
)

logger = logging.getLogger("WebVeilGemini")


class GeminiProvider:
    """Gemini reasoning provider using google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.6-flash"):
        self._token_usage = TokenUsage()
        self._model_name = model

        try:
            from google import genai
            from google.genai import types

            if not api_key:
                from webveil.config import config
                api_key = config.gemini_api_key

            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")

            self._client = genai.Client(api_key=api_key)
            self._types = types
            logger.info(f"[Gemini] Initialized with model {model}")
        except Exception as e:
            logger.error(f"[Gemini] Failed to initialize: {e}")
            raise

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """Send sanitized context to Gemini and get action plan."""
        user_message = build_reasoning_context(
            task, world_model, action_history, error_context
        )

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=[
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_message}]}
                ],
                config=self._types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
            )

            raw_text = response.text or ""

            # Track token usage
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                self._token_usage.add(
                    input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0) or 0,
                    output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0) or 0,
                )
            else:
                # Estimate if metadata not available
                self._token_usage.add(
                    input_tokens=len(user_message) // 4,
                    output_tokens=len(raw_text) // 4,
                )

            logger.info(f"[Gemini] Response received ({len(raw_text)} chars)")
            return parse_action_plan(raw_text)

        except Exception as e:
            logger.error(f"[Gemini] API call failed: {e}")
            from webveil.core.models.schema import BrowserAction, ActionType
            return ActionPlan(
                actions=[BrowserAction(action=ActionType.WAIT, thought=f"Gemini API error: {str(e)[:100]}")],
                thought=f"API error, waiting to retry: {str(e)[:100]}",
            )

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    @property
    def provider_name(self) -> str:
        return f"Gemini ({self._model_name})"
