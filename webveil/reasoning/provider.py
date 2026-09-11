"""
Reasoning Provider Protocol & Factory.
Defines the interface that all reasoning backends must implement.
The provider proposes; the local client decides.
"""

import os
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
3. NEVER invent real personal data. Use only placeholder tokens or realistic test values.
4. Return a JSON action plan with ALL necessary actions to advance or complete the task (up to 12 actions).
   - When asked to fill out a form and submit, include the COMPLETE sequence of actions:
     a) Type all text, email, phone, password, and date fields.
     b) Select appropriate dropdown options (action="select", node_id, value).
     c) Click any required agreement or consent checkboxes (action="click", node_id).
     d) Click the submit button (action="click", node_id) as the final step.
   - Do NOT stop midway through a form. If a form is presented, fill ALL available fields and submit.
5. If all steps are complete or after clicking submit, include action="done" as the final action.
6. Your "thought" field should explain your reasoning for EACH action and summarize what was accomplished.

ACTION TYPES:
- click: Click element by node_id (buttons, links, checkboxes). Required: node_id. To check a checkbox, click it.
- type: Type text into element (text, email, password, date). Required: node_id, text. For date fields, use YYYY-MM-DD (e.g., "1995-05-15").
- select: Select dropdown option. Required: node_id, value. Choose an option value from the select element's options list.
- navigate: Go to URL. Required: url
- scroll: Scroll the page. Optional: direction ("up"/"down"), amount (pixels)
- keypress: Press a key. Required: key (e.g., "Enter", "Tab", "Escape")
- wait: Wait for page to load. No parameters needed.
- done: Task is complete. Include thought explaining what was accomplished.

DOM FORMAT:
Each interactive element is shown as:
[node_id] <tag id='...' type='...' placeholder='...' value='...'>"text or options" [interactive]

RESPOND WITH ONLY VALID JSON in this exact format:
{
  "thought": "Overall reasoning for this plan",
  "actions": [
    {"action": "type", "node_id": 45, "text": "John Doe", "thought": "Filling full name"},
    {"action": "type", "node_id": 47, "text": "[EMAIL_1]", "thought": "Filling email placeholder"},
    {"action": "type", "node_id": 49, "text": "9876543210", "thought": "Filling phone number"},
    {"action": "type", "node_id": 51, "text": "[AADHAAR_1]", "thought": "Filling Aadhaar identifier"},
    {"action": "type", "node_id": 53, "text": "[PASSWORD_1]", "thought": "Filling password"},
    {"action": "select", "node_id": 55, "value": "aadhaar", "thought": "Selecting document type"},
    {"action": "type", "node_id": 57, "text": "1995-05-15", "thought": "Filling date of birth"},
    {"action": "click", "node_id": 58, "thought": "Checking consent box"},
    {"action": "click", "node_id": 60, "thought": "Submitting the form"},
    {"action": "done", "thought": "Form completed and submitted"}
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


def parse_action_plan(raw_response: str, max_actions: int = 15) -> ActionPlan:
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
                    # Try partial regex extraction before giving up
                    thought_m = re.search(r'"thought"\s*:\s*"([^"]+)"', raw_response)
                    action_m = re.search(r'"action"\s*:\s*"([a-zA-Z_]+)"', raw_response)
                    if thought_m:
                        th = thought_m.group(1)
                        act_str = action_m.group(1) if action_m else "done"
                        try:
                            act_type = ActionType(act_str.lower())
                        except ValueError:
                            act_type = ActionType.DONE
                        node_m = re.search(r'"node_id"\s*:\s*(\d+)', raw_response)
                        nid = int(node_m.group(1)) if node_m else None
                        return ActionPlan(
                            actions=[BrowserAction(action=act_type, node_id=nid, thought=th)],
                            thought=th,
                        )
                    logger.error(f"[Reasoning] Failed to parse JSON candidate: {json_candidate[:200]}")
                    return ActionPlan(
                        actions=[BrowserAction(action=ActionType.WAIT, thought="Failed to parse LLM response")],
                        thought="Parse error — waiting for retry",
                    )
        else:
            # Check if LLM answered in plain English thought without JSON wrapper
            thought_m = re.search(r'"thought"\s*:\s*"([^"]+)"', raw_response)
            if thought_m:
                th = thought_m.group(1)
                return ActionPlan(actions=[BrowserAction(action=ActionType.DONE, thought=th)], thought=th)
            elif len(text) > 10 and not text.startswith("{"):
                return ActionPlan(actions=[BrowserAction(action=ActionType.DONE, thought=text[:300])], thought=text[:300])

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



# ─── 3-Tier Escalation Cascade ──────────────────────────────────────────

def _is_error_plan(plan: Optional[ActionPlan]) -> bool:
    if not plan:
        return True
    if getattr(plan, "provider_used", "").endswith(": Error)"):
        return True
    thought = (plan.thought or "").lower()
    error_keywords = [
        "api error", "quota exceeded", "resource_exhausted", "rate limit",
        "429", "unauthorized", "failed to parse", "parse error", "no json in llm"
    ]
    return any(k in thought for k in error_keywords)


class CascadeReasoningProvider:
    """
    3-Tier Escalation Cascade for Privacy-Preserving Browser Reasoning:

    1. Tier 1 (Primary, Local, Always Tried First):
       - Local Ollama daemon on http://localhost:11434 (model: llama3.1).
       - Zero API keys required, zero reasoning network egress.

    2. Tier 2 (Backup, Free Hosted Open-Weight):
       - OpenRouter free tier (model: nvidia/nemotron-3-ultra:free or openrouter/free).
       - Free API key, used if local Ollama times out, is offline, or errors.

    3. Tier 3 (Final Backup, Google Free Tier):
       - Google Gemini 2.5 Flash free tier (gemini-2.5-flash).
       - Free API key, used only if Tier 1 and Tier 2 are unavailable or rate-limited.

    Safety Net:
       - Local deterministic mock if completely offline or without credentials.
    """

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        openrouter_key: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        gemini_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
    ):
        from webveil.config import config

        self._active_tier: str = "Local (Ollama)"
        self._token_usage = TokenUsage()

        # Initialize Tier 1: Local Ollama
        try:
            from webveil.reasoning.providers.ollama_provider import OllamaProvider
            self._ollama: Optional[OllamaProvider] = OllamaProvider(
                base_url=ollama_url or config.ollama_base_url,
                model=ollama_model or config.ollama_model,
                timeout=float(os.getenv("OLLAMA_TIMEOUT", "25.0")),
            )
        except Exception as e:
            logger.warning(f"[Cascade] Ollama provider init failed: {e}")
            self._ollama = None

        # Initialize Tier 2: OpenRouter Free
        or_key = openrouter_key or config.openrouter_api_key
        or_model = openrouter_model or config.openrouter_model or "nvidia/nemotron-3-ultra-550b-a55b:free"
        if or_key:
            try:
                from webveil.reasoning.providers.openrouter_provider import OpenRouterProvider
                self._openrouter: Optional[OpenRouterProvider] = OpenRouterProvider(
                    api_key=or_key,
                    model=or_model,
                )
            except Exception as e:
                logger.warning(f"[Cascade] OpenRouter provider init failed: {e}")
                self._openrouter = None
        else:
            self._openrouter = None

        # Initialize Tier 3: Gemini Free Tier
        gem_key = gemini_key or config.gemini_api_key
        gem_model = gemini_model or config.gemini_model or "gemini-2.5-flash"
        if gem_key:
            try:
                from webveil.reasoning.providers.gemini_provider import GeminiProvider
                self._gemini: Optional[GeminiProvider] = GeminiProvider(
                    api_key=gem_key,
                    model=gem_model,
                )
            except Exception as e:
                logger.warning(f"[Cascade] Gemini provider init failed: {e}")
                self._gemini = None
        else:
            self._gemini = None

        # Initialize Fallback Mock
        from webveil.reasoning.providers.mock_provider import MockProvider
        self._mock = MockProvider()

        logger.info(
            f"[Cascade] 3-Tier cascade initialized: "
            f"Tier 1 (Local Ollama: {getattr(self._ollama, '_model_name', 'None')}) -> "
            f"Tier 2 (OpenRouter: {or_model if self._openrouter else 'No Key'}) -> "
            f"Tier 3 (Gemini: {gem_model if self._gemini else 'No Key'})"
        )

    @property
    def provider_name(self) -> str:
        return f"Cascade [{self._active_tier}]"

    @property
    def active_tier(self) -> str:
        return self._active_tier

    @property
    def token_usage(self) -> TokenUsage:
        tot = TokenUsage()
        for p in [self._ollama, self._openrouter, self._gemini]:
            if p and hasattr(p, "token_usage"):
                tot.input_tokens += p.token_usage.input_tokens
                tot.output_tokens += p.token_usage.output_tokens
                tot.total_calls += p.token_usage.total_calls
        return tot

    def reason(
        self,
        task: str,
        world_model: SanitizedWorldModel,
        action_history: List[ActionResult],
        error_context: Optional[str] = None,
    ) -> ActionPlan:
        """
        Escalation order:
        1. Local Ollama (Zero key, zero egress)
        2. OpenRouter Free (Nemotron 3 Ultra)
        3. Gemini 2.5 Flash Free Tier
        4. Local Mock
        """
        # ── Tier 1: Local Ollama (Primary) ──
        if self._ollama and getattr(self._ollama, "is_available", lambda: True)():
            try:
                logger.info("[Cascade] Trying Tier 1: Local Ollama (zero-network egress)...")
                plan = self._ollama.reason(task, world_model, action_history, error_context)
                if plan and not _is_error_plan(plan):
                    plan.provider_used = "Local (Ollama)"
                    self._active_tier = "Local (Ollama)"
                    return plan
                logger.warning(f"[Cascade] Tier 1 returned error or invalid plan: {plan.thought if plan else 'None'}. Escalating...")
            except Exception as e:
                logger.warning(f"[Cascade] Tier 1 (Ollama) unavailable: {e}. Escalating to Tier 2 (OpenRouter)...")
        elif self._ollama:
            logger.info("[Cascade] Tier 1 (Ollama daemon offline). Instantly escalating to Tier 2...")

        # ── Tier 2: OpenRouter Free (Backup) ──
        if self._openrouter:
            try:
                logger.info("[Cascade] Trying Tier 2: OpenRouter (free open-weight model)...")
                plan = self._openrouter.reason(task, world_model, action_history, error_context)
                if plan and not _is_error_plan(plan):
                    plan.provider_used = "Fallback (OpenRouter)"
                    self._active_tier = "Fallback (OpenRouter)"
                    return plan
                logger.warning(f"[Cascade] Tier 2 returned error or rate limit: {plan.thought if plan else 'None'}. Escalating...")
            except Exception as e:
                logger.warning(f"[Cascade] Tier 2 (OpenRouter) failed: {e}. Escalating to Tier 3 (Gemini)...")

        # ── Tier 3: Gemini 2.5 Flash Free Tier (Final Backup) ──
        if self._gemini:
            try:
                logger.info("[Cascade] Trying Tier 3: Gemini 2.5 Flash Free Tier...")
                plan = self._gemini.reason(task, world_model, action_history, error_context)
                if plan and not _is_error_plan(plan):
                    plan.provider_used = "Fallback (Gemini)"
                    self._active_tier = "Fallback (Gemini)"
                    return plan
                logger.warning(f"[Cascade] Tier 3 returned error or rate limit: {plan.thought if plan else 'None'}.")
            except Exception as e:
                logger.warning(f"[Cascade] Tier 3 (Gemini) failed: {e}.")

        # ── Safety Net: Local Mock ──
        logger.warning("[Cascade] All reasoning tiers exhausted. Falling back to local deterministic mock.")
        plan = self._mock.reason(task, world_model, action_history, error_context)
        plan.provider_used = "Local (Mock Fallback)"
        self._active_tier = "Local (Mock Fallback)"
        return plan


# ─── Provider Factory ──────────────────────────────────────────────────

def create_provider(provider_name: str, **kwargs) -> ReasoningProvider:
    """Create a reasoning provider by name."""
    p_name = (provider_name or "").strip().lower()
    if p_name in ("cascade", "default", "local-first", "cascade-provider"):
        return CascadeReasoningProvider(**kwargs)
    elif p_name == "ollama":
        from webveil.reasoning.providers.ollama_provider import OllamaProvider
        return OllamaProvider(**kwargs)
    elif p_name == "gemini":
        from webveil.reasoning.providers.gemini_provider import GeminiProvider
        return GeminiProvider(**kwargs)
    elif p_name == "openrouter":
        from webveil.reasoning.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(**kwargs)
    elif p_name == "openai":
        from webveil.reasoning.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    elif p_name == "mock":
        from webveil.reasoning.providers.mock_provider import MockProvider
        return MockProvider()
    else:
        logger.warning(f"Unknown provider '{provider_name}', defaulting to 3-tier cascade")
        return CascadeReasoningProvider(**kwargs)

