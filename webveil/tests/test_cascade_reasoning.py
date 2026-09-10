"""
Unit and Integration Tests for WebVeil 3-Tier Escalation Cascade.
Validates:
  Tier 1: Local Ollama (zero-key, zero-egress, primary)
  Tier 2: OpenRouter free tier (Nemotron 3 Ultra backup)
  Tier 3: Gemini 2.5 Flash free tier (Google backup)
  Safety Net: Deterministic local mock fallback
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from webveil.core.models.schema import (
    ActionPlan, BrowserAction, ActionType, SanitizedWorldModel, ActionResult
)
from webveil.reasoning.provider import (
    CascadeReasoningProvider, create_provider
)
from webveil.api.reasoning_server import app, _provider_cache


@pytest.fixture(autouse=True)
def clear_caches():
    _provider_cache.clear()
    yield
    _provider_cache.clear()


def make_dummy_world_model():
    return SanitizedWorldModel(
        url="https://isro.gov.in",
        sanitized_url="https://isro.gov.in",
        title="ISRO - Government of India",
        sanitized_dom=[],
        formatted_dom="[1] <button>Missions</button>",
    )


class TestCascadeReasoningProvider:
    """Test suite verifying the 3-tier cascade escalation logic."""

    def test_tier1_ollama_primary_success(self):
        """Tier 1 (Local Ollama) succeeds -> zero network egress for reasoning."""
        cascade = CascadeReasoningProvider()
        mock_ollama = MagicMock()
        mock_ollama.reason.return_value = ActionPlan(
            thought="Ollama local reasoning succeeded",
            actions=[BrowserAction(action=ActionType.CLICK, node_id=1, thought="Click missions")],
        )
        cascade._ollama = mock_ollama
        cascade._openrouter = MagicMock()
        cascade._gemini = MagicMock()

        plan = cascade.reason("Find missions", make_dummy_world_model(), [])

        assert plan.provider_used == "Local (Ollama)"
        assert "Ollama local reasoning succeeded" in plan.thought
        assert cascade.active_tier == "Local (Ollama)"
        # Confirm fallbacks were NOT touched
        cascade._openrouter.reason.assert_not_called()
        cascade._gemini.reason.assert_not_called()

    def test_tier1_down_escalates_to_tier2_openrouter(self):
        """Tier 1 (Ollama) is offline/times out -> gracefully escalates to Tier 2 (OpenRouter Nemotron)."""
        cascade = CascadeReasoningProvider()
        mock_ollama = MagicMock()
        mock_ollama.reason.side_effect = ConnectionError("Ollama daemon unreachable on localhost:11434")
        cascade._ollama = mock_ollama

        mock_openrouter = MagicMock()
        mock_openrouter.reason.return_value = ActionPlan(
            thought="OpenRouter Nemotron 3 Ultra responded",
            actions=[BrowserAction(action=ActionType.CLICK, node_id=1, thought="Click missions")],
        )
        cascade._openrouter = mock_openrouter
        cascade._gemini = MagicMock()

        plan = cascade.reason("Find missions", make_dummy_world_model(), [])

        assert plan.provider_used == "Fallback (OpenRouter)"
        assert "OpenRouter Nemotron 3 Ultra responded" in plan.thought
        assert cascade.active_tier == "Fallback (OpenRouter)"
        # Confirm Tier 3 was not needed
        cascade._gemini.reason.assert_not_called()

    def test_tier1_and_tier2_rate_limited_escalates_to_tier3_gemini(self):
        """Tier 1 down + Tier 2 rate-limited (429) -> escalates to Tier 3 (Gemini 2.5 Flash free tier)."""
        cascade = CascadeReasoningProvider()
        mock_ollama = MagicMock()
        mock_ollama.reason.side_effect = TimeoutError("Ollama timed out")
        cascade._ollama = mock_ollama

        mock_openrouter = MagicMock()
        # OpenRouter returns 429 error plan
        mock_openrouter.reason.return_value = ActionPlan(
            thought="OpenRouter API error: 429 Rate limit exceeded / Quota exhausted",
            actions=[BrowserAction(action=ActionType.WAIT)],
            provider_used="Fallback (OpenRouter: Error)",
        )
        cascade._openrouter = mock_openrouter

        mock_gemini = MagicMock()
        mock_gemini.reason.return_value = ActionPlan(
            thought="Gemini 2.5 Flash free tier answered",
            actions=[BrowserAction(action=ActionType.CLICK, node_id=1)],
        )
        cascade._gemini = mock_gemini

        plan = cascade.reason("Find missions", make_dummy_world_model(), [])

        assert plan.provider_used == "Fallback (Gemini)"
        assert "Gemini 2.5 Flash" in plan.thought
        assert cascade.active_tier == "Fallback (Gemini)"

    def test_all_tiers_down_falls_back_to_local_mock(self):
        """If all tiers fail or are offline, returns safe local deterministic mock plan."""
        cascade = CascadeReasoningProvider()
        mock_ollama = MagicMock()
        mock_ollama.reason.side_effect = ConnectionError("Connection refused")
        cascade._ollama = mock_ollama

        mock_openrouter = MagicMock()
        mock_openrouter.reason.side_effect = RuntimeError("OpenRouter auth failed")
        cascade._openrouter = mock_openrouter

        mock_gemini = MagicMock()
        mock_gemini.reason.side_effect = RuntimeError("Gemini quota exceeded")
        cascade._gemini = mock_gemini

        plan = cascade.reason("Find missions", make_dummy_world_model(), [])

        assert plan is not None
        assert len(plan.actions) > 0
        assert plan.provider_used == "Local (Mock Fallback)"
        assert cascade.active_tier == "Local (Mock Fallback)"

    def test_factory_creation_and_defaults(self):
        """create_provider('cascade') properly instantiates CascadeReasoningProvider."""
        provider = create_provider("cascade")
        assert isinstance(provider, CascadeReasoningProvider)
        assert "Cascade" in provider.provider_name


class TestReasoningServerCascadeIntegration:
    """Verify reasoning server endpoints interact seamlessly with the cascade."""

    def test_health_endpoint_reports_cascade_status(self):
        client = TestClient(app)
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "active_tier" in data
        assert "Cascade" in data["provider"] or "Local" in data["active_tier"]

    def test_reason_endpoint_returns_provider_used(self):
        client = TestClient(app)
        with patch("webveil.api.reasoning_server.create_provider") as mock_create:
            mock_p = MagicMock()
            mock_p.provider_name = "Cascade [Local (Ollama)]"
            mock_p.active_tier = "Local (Ollama)"
            mock_p.reason.return_value = ActionPlan(
                thought="Found launch schedules locally",
                actions=[BrowserAction(action=ActionType.CLICK, node_id=2, thought="Navigating")],
                provider_used="Local (Ollama)",
            )
            mock_create.return_value = mock_p

            res = client.post(
                "/api/reason",
                json={
                    "task": "Find upcoming launches",
                    "url": "https://isro.gov.in",
                    "title": "ISRO",
                    "dom": [{"node_id": 2, "tag_name": "a", "text_content": "Launches", "is_interactive": True}],
                },
            )

            assert res.status_code == 200
            data = res.json()
            assert data["provider_used"] == "Local (Ollama)"
            assert "Found launch schedules locally" in data["thought"]
            assert len(data["actions"]) == 1
            assert data["actions"][0]["node_id"] == 2
