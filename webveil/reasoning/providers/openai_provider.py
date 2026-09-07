"""
OpenAI Reasoning Provider.
Uses the openai SDK. Also works with Ollama via base_url swap.
"""

import logging
from typing import List, Optional

from webveil.core.models.schema import (
    ActionPlan, ActionResult, SanitizedWorldModel, TokenUsage, BrowserAction, ActionType
)
from webveil.reasoning.provider import (
    SYSTEM_PROMPT, build_reasoning_context, parse_action_plan
)

logger = logging.getLogger("WebVeilOpenAI")


class OpenAIProvider:
    """OpenAI reasoning provider. Works with OpenAI API and Ollama (via base_url)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self._token_usage = TokenUsage()
        self._model_name = model

        try:
            from openai import OpenAI

            if not api_key and not base_url:
                from webveil.config import config
                api_key = config.openai_api_key
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not set")

            client_kwargs = {}
            if api_key:
                client_kwargs["api_key"] = api_key
            if base_url:
                client_kwargs["base_url"] = base_url
                # Ollama doesn't need a real API key
                if "api_key" not in client_kwargs:
                    client_kwargs["api_key"] = "ollama"

            self._client = OpenAI(**client_kwargs)
            provider_type = "Ollama" if base_url and "11434" in base_url else "OpenAI"
            logger.info(f"[{provider_type}] Initialized with model {model}")

        except Exception as e:
            logger.error(f"[OpenAI] Failed to initialize: {e}")
            raise

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """Send sanitized context to OpenAI and get action plan."""
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

            raw_text = response.choices[0].message.content or ""

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

            logger.info(f"[OpenAI] Response received ({len(raw_text)} chars)")
            return parse_action_plan(raw_text)

        except Exception as e:
            logger.error(f"[OpenAI] API call failed: {e}")
            return ActionPlan(
                actions=[BrowserAction(action=ActionType.WAIT, thought=f"OpenAI API error: {str(e)[:100]}")],
                thought=f"API error, waiting to retry: {str(e)[:100]}",
            )

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    @property
    def provider_name(self) -> str:
        return f"OpenAI ({self._model_name})"


class OllamaProvider(OpenAIProvider):
    """Ollama provider — thin wrapper over OpenAI provider with local base_url."""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434/v1"):
        super().__init__(api_key=None, model=model, base_url=base_url)

    @property
    def provider_name(self) -> str:
        return f"Ollama ({self._model_name})"
