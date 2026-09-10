"""
OpenRouter Reasoning Provider.
Connects WebVeil to OpenRouter API (https://openrouter.ai/api/v1)
using OpenAI-compatible client interface and structured JSON action outputs.
"""

import logging
from typing import List, Optional

from webveil.core.models.schema import (
    ActionPlan, ActionResult, SanitizedWorldModel, TokenUsage, BrowserAction, ActionType
)
from webveil.reasoning.provider import (
    SYSTEM_PROMPT, build_reasoning_context, parse_action_plan
)

logger = logging.getLogger("WebVeilOpenRouter")


class OpenRouterProvider:
    """
    OpenRouter reasoning provider.
    Enables plug-and-play access to free and paid models hosted on OpenRouter
    (e.g., 'openrouter/free', 'google/gemini-2.0-flash-exp:free', 'meta-llama/llama-3.3-70b-instruct:free').
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        site_url: str = "https://github.com/armash66/veil-agent",
        site_name: str = "WebVeil",
    ):
        from webveil.config import config
        self._token_usage = TokenUsage()
        self._model_name = model or config.openrouter_model or "nvidia/nemotron-3-ultra-550b-a55b:free"

        try:
            from openai import OpenAI

            if not api_key:
                from webveil.config import config
                api_key = config.openrouter_api_key

            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set")

            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": site_url,
                    "X-Title": site_name,
                }
            )
            logger.info(f"[OpenRouter] Initialized with model '{model}'")

        except Exception as e:
            logger.error(f"[OpenRouter] Initialization failed: {e}")
            raise

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """Send sanitized context to OpenRouter and get structured action plan."""
        user_message = build_reasoning_context(
            task, world_model, action_history, error_context
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1024,
            )

            choice = response.choices[0] if response.choices else None
            msg = choice.message if choice else None
            raw_text = (msg.content if msg else "") or ""

            # Track token usage
            if response.usage:
                self._token_usage.add(
                    input_tokens=response.usage.prompt_tokens or 0,
                    output_tokens=response.usage.completion_tokens or 0,
                )
            else:
                self._token_usage.add(
                    input_tokens=len(user_message) // 4,
                    output_tokens=len(raw_text) // 4,
                )

            logger.info(f"[OpenRouter] Response received ({len(raw_text)} chars)")
            plan = parse_action_plan(raw_text)
            plan.provider_used = "Fallback (OpenRouter)"
            return plan

        except Exception as e:
            err_str = str(e)
            logger.error(f"[OpenRouter] API call failed: {err_str[:200]}")
            plan = ActionPlan(
                actions=[BrowserAction(action=ActionType.WAIT, thought=f"OpenRouter error: {err_str[:100]}")],
                thought=f"OpenRouter API error: {err_str[:120]}",
            )
            plan.provider_used = "Fallback (OpenRouter: Error)"
            return plan

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    @property
    def provider_name(self) -> str:
        return f"OpenRouter ({self._model_name})"
