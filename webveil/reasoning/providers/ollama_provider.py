"""
Ollama Reasoning Provider.
Connects WebVeil to a local Ollama instance (default: http://localhost:11434)
for 100% self-hosted, offline, zero-key, zero-network-egress browser reasoning.
"""

import logging
from typing import List, Optional
import httpx

from webveil.core.models.schema import (
    ActionPlan, ActionResult, SanitizedWorldModel, TokenUsage
)
from webveil.reasoning.provider import (
    SYSTEM_PROMPT, build_reasoning_context, parse_action_plan
)

logger = logging.getLogger("WebVeilOllama")


class OllamaProvider:
    """
    Ollama local reasoning provider.
    Runs completely on-device. Proposes action plans without contacting any cloud API.
    Zero keys required, zero reasoning network egress.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 12.0,
    ):
        from webveil.config import config
        self._base_url = (base_url or config.ollama_base_url or "http://localhost:11434").rstrip("/")
        self._model_name = model or config.ollama_model or "llama3.1"
        self._timeout = timeout
        self._token_usage = TokenUsage()
        logger.info(f"[Ollama] Initialized at {self._base_url} with model '{self._model_name}' (timeout: {self._timeout}s)")

    @property
    def provider_name(self) -> str:
        return f"Ollama ({self._model_name})"

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self._base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """Send sanitized context to local Ollama daemon and get structured action plan."""
        user_message = build_reasoning_context(
            task, world_model, action_history, error_context
        )

        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )

                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")

                data = response.json()
                raw_text = data.get("message", {}).get("content", "")

                prompt_eval = data.get("prompt_eval_count", 0) or (len(user_message) // 4)
                eval_count = data.get("eval_count", 0) or (len(raw_text) // 4)
                self._token_usage.add(input_tokens=prompt_eval, output_tokens=eval_count)

                logger.info(f"[Ollama] Response received ({len(raw_text)} chars, {eval_count} tokens)")
                plan = parse_action_plan(raw_text)
                plan.provider_used = "Local (Ollama)"
                return plan

        except (httpx.ConnectError, httpx.ConnectTimeout) as conn_err:
            logger.warning(f"[Ollama] Connection failed to {self._base_url}: {conn_err}")
            raise ConnectionError(f"Ollama daemon unreachable at {self._base_url}") from conn_err
        except httpx.TimeoutException as timeout_err:
            logger.warning(f"[Ollama] Inference timed out after {self._timeout}s: {timeout_err}")
            raise TimeoutError(f"Ollama inference timed out ({self._timeout}s)") from timeout_err
        except Exception as e:
            logger.error(f"[Ollama] Reason error: {e}")
            raise
