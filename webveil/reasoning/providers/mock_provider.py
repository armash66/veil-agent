"""
Mock Reasoning Provider.
Adapted from V0 VLMServerReasoningEngine for offline testing and fallback.
"""

import logging
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import (
    ActionPlan, BrowserAction, ActionType, ActionResult,
    SanitizedWorldModel, TokenUsage
)

logger = logging.getLogger("WebVeilMockProvider")


class MockProvider:
    """
    Offline mock reasoning engine.
    Uses heuristic DOM matching for form-filling tasks.
    Used when no API key is configured or for unit testing.
    """

    def __init__(self):
        self._token_usage = TokenUsage()

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """Heuristic-based form filling using sanitized DOM text."""
        dom = world_model.formatted_dom
        lines = dom.split("\n")
        interactive_nodes = []

        for line in lines:
            if not line.strip() or not line.startswith("["):
                continue
            try:
                node_id = int(line.split("]")[0].replace("[", ""))
                rest = line.split("]", 1)[1].strip().lower()
                interactive_nodes.append({"node_id": node_id, "raw_line": rest})
            except Exception:
                continue

        typed_ids = set(
            r.action.node_id for r in action_history
            if r.action.action == ActionType.TYPE
        )
        clicked_ids = set(
            r.action.node_id for r in action_history
            if r.action.action == ActionType.CLICK
        )

        actions = []
        for item in interactive_nodes:
            nid = item["node_id"]
            line = item["raw_line"]

            if "name" in line and "input" in line and nid not in typed_ids and "email" not in line and "phone" not in line and "aadhaar" not in line and "password" not in line and "date" not in line and "checkbox" not in line and "radio" not in line and "select" not in line:
                actions.append(BrowserAction(
                    action=ActionType.TYPE, node_id=nid,
                    text="WebVeil Test User",
                    thought="Typing name into text field (mock)"
                ))

            elif ("email" in line or "[email_" in line) and "input" in line and nid not in typed_ids:
                actions.append(BrowserAction(
                    action=ActionType.TYPE, node_id=nid,
                    text="[EMAIL_1]",
                    thought="Typing email placeholder (mock)"
                ))

            elif ("phone" in line or "[phone_" in line) and "input" in line and nid not in typed_ids:
                actions.append(BrowserAction(
                    action=ActionType.TYPE, node_id=nid,
                    text="[PHONE_1]",
                    thought="Typing phone placeholder (mock)"
                ))

            elif ("aadhaar" in line or "[aadhaar_" in line) and "input" in line and nid not in typed_ids:
                actions.append(BrowserAction(
                    action=ActionType.TYPE, node_id=nid,
                    text="[AADHAAR_1]",
                    thought="Typing Aadhaar placeholder (mock)"
                ))

            elif ("password" in line or "[password_" in line) and "input" in line and nid not in typed_ids:
                actions.append(BrowserAction(
                    action=ActionType.TYPE, node_id=nid,
                    text="[PASSWORD_1]",
                    thought="Typing password placeholder (mock)"
                ))

            elif ("submit" in line or "button" in line) and nid not in clicked_ids:
                actions.append(BrowserAction(
                    action=ActionType.CLICK, node_id=nid,
                    thought="Clicking submit button (mock)"
                ))

        if not actions:
            actions = [BrowserAction(action=ActionType.DONE, thought="No more actions available (mock)")]

        self._token_usage.add(input_tokens=0, output_tokens=0)

        return ActionPlan(
            actions=actions[:5],
            thought="Mock provider: heuristic form-filling based on DOM structure",
        )

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    @property
    def provider_name(self) -> str:
        return "Mock (offline)"
