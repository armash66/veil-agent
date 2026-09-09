"""
Unit tests for OpenRouter Reasoning Provider and Dual-Provider Switching.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from webveil.config import WebVeilConfig
from webveil.core.models.schema import SanitizedWorldModel, ActionType, DOMNode
from webveil.reasoning.provider import create_provider
from webveil.reasoning.providers.openrouter_provider import OpenRouterProvider


class TestOpenRouterProvider(unittest.TestCase):

    def test_openrouter_provider_initialization(self):
        """Verify OpenRouter provider initializes with expected model and endpoint."""
        provider = OpenRouterProvider(api_key="sk-or-test-key-12345", model="openrouter/free")
        self.assertEqual(provider.provider_name, "OpenRouter (openrouter/free)")
        self.assertEqual(provider.token_usage.total_tokens, 0)

    @patch("openai.OpenAI")
    def test_openrouter_reasoning_success(self, mock_openai_cls):
        """Verify OpenRouter sends structured request and parses action plan."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = """{
            "thought": "Navigating to requested destination",
            "actions": [
                {"action": "navigate", "url": "https://www.isro.gov.in", "thought": "Opening ISRO site"}
            ]
        }"""
        mock_completion.choices = [mock_choice]
        mock_completion.usage.prompt_tokens = 120
        mock_completion.usage.completion_tokens = 45
        mock_client.chat.completions.create.return_value = mock_completion

        provider = OpenRouterProvider(api_key="sk-or-test-key", model="openrouter/free")
        world_model = SanitizedWorldModel(
            url="https://console.aws.amazon.com",
            sanitized_url="https://console.aws.amazon.com",
            title="AWS Management Console",
            sanitized_dom=[],
            formatted_dom="",
        )

        plan = provider.reason(
            task="Open the ISRO website",
            world_model=world_model,
            action_history=[],
        )

        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action, ActionType.NAVIGATE)
        self.assertEqual(plan.actions[0].url, "https://www.isro.gov.in")
        self.assertEqual(provider.token_usage.total_tokens, 165)

    def test_factory_and_dual_provider_config(self):
        """Verify factory instantiates openrouter without breaking gemini fallback."""
        openrouter_prov = create_provider("openrouter", api_key="sk-or-test-key", model="openrouter/free")
        self.assertIsInstance(openrouter_prov, OpenRouterProvider)

        # Test config dual-provider awareness
        cfg = WebVeilConfig()
        cfg.openrouter_api_key = "sk-or-test"
        cfg.gemini_api_key = "test-gemini-key"
        cfg.provider = "openrouter"
        warnings = cfg.validate()
        self.assertEqual(len(warnings), 0)
        self.assertEqual(cfg.provider, "openrouter")


if __name__ == "__main__":
    unittest.main()
