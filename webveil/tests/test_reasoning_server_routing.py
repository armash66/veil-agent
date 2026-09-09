import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from webveil.api.reasoning_server import app, _provider_cache
from webveil.core.models.schema import ActionPlan, BrowserAction, ActionType

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    _provider_cache.clear()
    yield
    _provider_cache.clear()


def test_reasoning_server_dynamic_provider_selection():
    """Verify that specifying provider='openrouter' in the request routes to OpenRouter."""
    with patch("webveil.api.reasoning_server.create_provider") as mock_create:
        mock_provider = MagicMock()
        mock_provider.provider_name = "OpenRouter (openrouter/free)"
        mock_provider.reason.return_value = ActionPlan(
            thought="Selected OpenRouter successfully",
            actions=[BrowserAction(action=ActionType.WAIT, thought="Waiting")],
        )
        mock_create.return_value = mock_provider

        response = client.post(
            "/api/reason",
            json={
                "task": "summarize this page",
                "url": "https://example.com",
                "title": "Example",
                "provider": "openrouter",
                "model": "openrouter/free",
                "dom": [
                    {
                        "node_id": 1,
                        "tag_name": "button",
                        "element_type": "button",
                        "text_content": "Click me",
                        "is_interactive": True,
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "Selected OpenRouter" in data["thought"]
        assert mock_create.call_args[0][0] == "openrouter"
        assert mock_create.call_args[1]["model"] == "openrouter/free"


def test_reasoning_server_gemini_429_fallback_to_openrouter():
    """Verify that when Gemini hits 429 quota exhausted, the server automatically falls back to OpenRouter."""
    with patch("webveil.api.reasoning_server.create_provider") as mock_create:
        gemini_mock = MagicMock()
        gemini_mock.provider_name = "Gemini (gemini-2.5-flash)"
        # Simulate Gemini 429 error returned
        gemini_mock.reason.return_value = ActionPlan(
            thought="API error (transient exhausted): 429 RESOURCE_EXHAUSTED",
            actions=[BrowserAction(action=ActionType.WAIT, thought="Error")],
        )

        openrouter_mock = MagicMock()
        openrouter_mock.provider_name = "OpenRouter (openrouter/free)"
        openrouter_mock.reason.return_value = ActionPlan(
            thought="Recovered via OpenRouter fallback",
            actions=[BrowserAction(action=ActionType.CLICK, node_id=1, thought="Clicked")],
        )

        def side_effect(provider_name, **kwargs):
            if provider_name == "gemini":
                return gemini_mock
            return openrouter_mock

        mock_create.side_effect = side_effect

        with patch("webveil.config.config.openrouter_api_key", "sk-or-test-key"):
            response = client.post(
                "/api/reason",
                json={
                    "task": "summarize this page",
                    "url": "https://example.com",
                    "title": "Example",
                    "provider": "gemini",
                    "dom": [],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "Recovered via OpenRouter fallback" in data["thought"]
            assert data["actions"][0]["action"] == "click"
