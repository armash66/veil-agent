"""
Reasoning Provider Protocol & Factory.
Defines the interface that all reasoning backends must implement.
The provider proposes; the local client decides.
"""

import logging
from typing import Protocol, runtime_checkable, List, Dict, Any, Optional

from webveil.core.models.schema import (
    ActionPlan, BrowserAction, ActionType, ActionResult,
    SanitizedWorldModel, TokenUsage
)

logger = logging.getLogger("WebVeilReasoning")

# ─── System Prompt (shared across all providers) ────────────────────────

SYSTEM_PROMPT = """You are WebVeil, a privacy-preserving browser agent. You help users complete browser tasks by observing sanitized page state and proposing actions.

IMPORTANT RULES:
1. You receive SANITIZED DOM — all sensitive data has been replaced with placeholders like [EMAIL_1], [PASSWORD_1], [AADHAAR_1]. These are NOT real values.
2. When you need to type sensitive data, use the EXACT placeholder token (e.g., type "[PASSWORD_1]" into a password field). The local client will safely restore the real value.
3. NEVER invent real personal data. Use only placeholder tokens or test values.
4. Return a JSON action plan with 1-5 actions. Each action has: action, node_id, text, key, url, value, direction, amount, thought.
5. If the task is complete, return a single action with action="done".
6. Your "thought" field should explain your reasoning for EACH action.

ACTION TYPES:
- click: Click element by node_id. Required: node_id
- type: Type text into element. Required: node_id, text
- navigate: Go to URL. Required: url
- scroll: Scroll the page. Optional: direction ("up"/"down"), amount (pixels)
- keypress: Press a key. Required: key (e.g., "Enter", "Tab", "Escape")
- select: Select dropdown option. Required: node_id, value
- wait: Wait for page to load. No parameters needed.
- done: Task is complete. Include thought explaining what was accomplished.

DOM FORMAT:
Each interactive element is shown as:
[node_id] <tag type='...' name='...' placeholder='...' value='...'>text</tag>

RESPOND WITH ONLY VALID JSON in this exact format:
{
  "thought": "Overall reasoning for this plan",
  "actions": [
    {"action": "click", "node_id": 5, "thought": "Clicking the search button"},
    {"action": "type", "node_id": 3, "text": "search query", "thought": "Typing search query"}
  ]
}"""


# ─── Provider Protocol ──────────────────────────────────────────────────

@runtime_checkable
class ReasoningProvider(Protocol):
    """
    Abstract reasoning interface.
    Remote reasoning proposes; local WebVeil decides execution.
    """

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """
        Given sanitized world state, propose an action plan.
        Returns 1-5 actions. Never sees raw PII.
        """
        ...

    @property
    def token_usage(self) -> TokenUsage:
        """Cumulative token usage for SIH metrics."""
        ...

    @property
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...


# ─── Context Builder (shared across providers) ─────────────────────────

def build_reasoning_context(
    task: str,
    world_model: SanitizedWorldModel,
    action_history: List[ActionResult],
    error_context: Optional[str] = None,
) -> str:
    """
    Build the user message content for the LLM.
    This is the sanitized context that leaves the device.
    """
    parts = []

    parts.append(f"TASK: {task}")
    parts.append(f"CURRENT URL: {world_model.url}")
    parts.append(f"PAGE TITLE: {world_model.title}")

    # Custom instruction context (from local instruction file)
    instruction_ctx = getattr(world_model, "instruction_context", None)
    if instruction_ctx:
        parts.append(f"\nUSER INSTRUCTIONS & CONSTRAINTS (from local instruction file):\n{instruction_ctx}")

    # Sanitized DOM (primary reasoning input)
    parts.append(f"\nSANITIZED DOM (interactive elements):\n{world_model.formatted_dom}")

    # Accessibility summary (supplementary)
    if world_model.a11y_summary:
        parts.append(f"\nACCESSIBILITY TREE SUMMARY:\n{world_model.a11y_summary[:2000]}")

    # OCR text (for visual content not in DOM)
    if world_model.ocr_summary:
        parts.append(f"\nVISUAL TEXT (from local OCR, not in DOM):\n{world_model.ocr_summary[:1000]}")

    # Privacy status
    if world_model.detected_pii_count > 0:
        parts.append(
            f"\nPRIVACY: {world_model.detected_pii_count} PII items detected and replaced with "
            f"placeholders: {', '.join(world_model.pii_categories_found)}"
        )

    # Action history (last 10 actions for context)
    if action_history:
        history_lines = []
        for r in action_history[-10:]:
            status = "✓" if r.success else f"✗ ({r.error})"
            a = r.action
            if a.action == ActionType.CLICK:
                history_lines.append(f"  Step {r.step_index}: click node [{a.node_id}] {status}")
            elif a.action == ActionType.TYPE:
                history_lines.append(f"  Step {r.step_index}: type '{a.text}' into [{a.node_id}] {status}")
            elif a.action == ActionType.NAVIGATE:
                history_lines.append(f"  Step {r.step_index}: navigate to {a.url} {status}")
            elif a.action == ActionType.KEYPRESS:
                history_lines.append(f"  Step {r.step_index}: press {a.key} {status}")
            else:
                history_lines.append(f"  Step {r.step_index}: {a.action.value} {status}")
        parts.append(f"\nACTION HISTORY:\n" + "\n".join(history_lines))

    # Error context for re-planning
    if error_context:
        parts.append(f"\nLAST ERROR (replan needed): {error_context}")

    return "\n".join(parts)


def parse_action_plan(raw_response: str, max_actions: int = 5) -> ActionPlan:
    """
    Parse LLM response into an ActionPlan.
    Handles JSON extraction from potentially noisy LLM output.
    """
    import json
    import re

    # Try to extract JSON from response
    text = raw_response.strip()

    # Remove markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try finding JSON block surrounded by ```json ... ``` or raw { ... }
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if not match:
            match = re.search(r'(\{[\s\S]*\})', text)
        
        if match:
            json_candidate = match.group(1) if match.lastindex else match.group(0)
            try:
                data = json.loads(json_candidate)
            except json.JSONDecodeError:
                # Fallback: extract "thought" and "actions" manually or sanitize trailing commas
                cleaned = re.sub(r',\s*([\}\]])', r'\1', json_candidate)
                try:
                    data = json.loads(cleaned)
                except json.JSONDecodeError:
                    logger.error(f"[Reasoning] Failed to parse JSON candidate: {json_candidate[:200]}")
                    return ActionPlan(
                        actions=[BrowserAction(action=ActionType.WAIT, thought="Failed to parse LLM response")],
                        thought="Parse error — waiting for retry",
                    )
        else:
            logger.error(f"[Reasoning] No JSON structure found in response: {text[:200]}")
            return ActionPlan(
                actions=[BrowserAction(action=ActionType.WAIT, thought="No JSON in LLM response")],
                thought="Parse error — waiting for retry",
            )

    # Parse actions from the JSON
    thought = data.get("thought", "")
    raw_actions = data.get("actions", [])

    if not raw_actions:
        return ActionPlan(
            actions=[BrowserAction(action=ActionType.DONE, thought="No actions proposed")],
            thought=thought,
        )

    actions = []
    for raw in raw_actions[:max_actions]:
        try:
            action_type = ActionType(raw.get("action", "wait"))
        except ValueError:
            continue

        action = BrowserAction(
            action=action_type,
            node_id=raw.get("node_id"),
            text=raw.get("text"),
            key=raw.get("key"),
            url=raw.get("url"),
            value=raw.get("value"),
            direction=raw.get("direction", "down"),
            amount=raw.get("amount", 300),
            thought=raw.get("thought", ""),
        )
        actions.append(action)

    if not actions:
        actions = [BrowserAction(action=ActionType.WAIT, thought="No valid actions parsed")]

    return ActionPlan(actions=actions, thought=thought)


# ─── Provider Factory ──────────────────────────────────────────────────

def create_provider(provider_name: str, **kwargs) -> ReasoningProvider:
    """Create a reasoning provider by name."""
    if provider_name == "gemini":
        from webveil.reasoning.providers.gemini_provider import GeminiProvider
        return GeminiProvider(**kwargs)
    elif provider_name == "openrouter":
        from webveil.reasoning.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(**kwargs)
    elif provider_name == "openai":
        from webveil.reasoning.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    elif provider_name == "mock":
        from webveil.reasoning.providers.mock_provider import MockProvider
        return MockProvider()
    else:
        logger.warning(f"Unknown provider '{provider_name}', falling back to mock")
        from webveil.reasoning.providers.mock_provider import MockProvider
        return MockProvider()
