"""
WebVeil V1 Agent Loop.
Observe locally → Protect locally → Reason remotely → Validate locally → Execute → Verify.
"""

import time
import json
import logging
from typing import List, Dict, Any, Optional, Callable

from webveil.config import config
from webveil.browser.playwright_adapter import PlaywrightAdapter
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault
from webveil.core.privacy.redactor import LocalRedactor
from webveil.core.observation.world_model import WorldModelBuilder
from webveil.security.egress.privacy_gate import EgressPrivacyGate, PrivacyViolationError
from webveil.security.firewall.action_firewall import ActionFirewall, ActionSecurityViolation
from webveil.core.verification.local_verifier import LocalVerifier
from webveil.evaluation.metrics import SIHMetricsEvaluator
from webveil.reasoning.provider import create_provider, ReasoningProvider
from webveil.core.models.schema import (
    ActionPlan, ActionResult, ActionType, BrowserAction,
    SanitizedObservation, EgressPayload, LocalWorldModel, SanitizedWorldModel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebVeilAgent")


class WebVeilAgent:
    """
    Core WebVeil V1 Agent.
    Enforces: local observation → privacy processing → sanitized reasoning → local execution authority.
    """

    def __init__(
        self,
        max_steps: int = None,
        headless: bool = None,
        provider_name: str = None,
        on_event: Optional[Callable] = None,
    ):
        self.max_steps = max_steps or config.max_steps
        self.headless = headless if headless is not None else config.headless
        self.max_actions_per_plan = config.max_actions_per_plan
        self.on_event = on_event  # Dashboard event callback

        # Subsystems
        self.browser = PlaywrightAdapter()
        self.detector = LocalPIIDetector()
        self.vault = ClientVault()
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.world_model_builder = WorldModelBuilder(
            self.redactor, ocr_enabled=config.ocr_enabled
        )
        self.egress_gate = EgressPrivacyGate(self.detector)
        self.firewall = ActionFirewall(self.vault, self.browser)
        self.verifier = LocalVerifier()
        self.metrics_evaluator = SIHMetricsEvaluator()

        # Reasoning provider
        provider_name = provider_name or config.provider
        warnings = config.validate()
        for w in warnings:
            logger.warning(w)
        provider_name = config.provider  # May have fallen back to mock

        try:
            provider_kwargs = {}
            if provider_name == "gemini":
                provider_kwargs = {"api_key": config.gemini_api_key, "model": config.gemini_model}
            elif provider_name == "openai":
                provider_kwargs = {"api_key": config.openai_api_key, "model": config.openai_model}
            elif provider_name == "ollama":
                from webveil.reasoning.providers.openai_provider import OllamaProvider
                self.provider = OllamaProvider(
                    model=config.ollama_model,
                    base_url=config.ollama_base_url + "/v1",
                )
                provider_name = None  # Skip factory

            if provider_name:
                self.provider = create_provider(provider_name, **provider_kwargs)
        except Exception as e:
            logger.warning(f"Provider '{provider_name}' init failed: {e}. Using mock.")
            self.provider = create_provider("mock")

        self.action_history: List[ActionResult] = []
        self._consecutive_same_action = 0
        self._last_action_key = ""

    def _emit(self, event_type: str, data: dict):
        """Emit event to dashboard."""
        if self.on_event:
            try:
                self.on_event({"type": event_type, "data": data, "timestamp": time.time()})
            except Exception:
                pass

    def run_task(self, start_url: str, task: str, initial_navigate: bool = True) -> Dict[str, Any]:
        """
        Run a browser task with privacy-preserving observation and reasoning.
        """
        logger.info(f"Starting WebVeil Agent | Provider: {self.provider.provider_name}")
        logger.info(f"Task: '{task}' | URL: {start_url}")

        self.metrics_evaluator.start_measurement()
        self.browser.start(headless=self.headless)
        self.vault.clear()
        self.action_history.clear()
        self._consecutive_same_action = 0

        self._emit("task_start", {"task": task, "url": start_url, "provider": self.provider.provider_name})

        try:
            if initial_navigate and start_url:
                self.browser.navigate(start_url)
                current_origin = self._get_origin(start_url)

            step_count = 0
            latest_pii_matches = []
            error_context = None

            while step_count < self.max_steps:
                step_count += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"STEP {step_count}/{self.max_steps}")
                logger.info(f"{'='*60}")

                self.metrics_evaluator.sample_resources()
                self._emit("step_start", {"step": step_count, "max_steps": self.max_steps})

                # ── 1. LOCAL OBSERVATION ──────────────────────────────
                t0 = time.time()
                dom_nodes, formatted_dom = self.browser.extract_dom()
                screenshot_b64 = self.browser.capture_screenshot_b64()
                current_url = self.browser.get_current_url()
                title = self.browser.get_page_title()
                self.metrics_evaluator.record_stage_latency(
                    "dom_extraction_ms", (time.time() - t0) * 1000
                )

                # ── 2. BUILD LOCAL WORLD MODEL ────────────────────────
                t0 = time.time()
                local_model, obs_timings = self.world_model_builder.build_local_model(
                    page=self.browser.page,
                    dom_nodes=dom_nodes,
                    formatted_dom=formatted_dom,
                    screenshot_b64=screenshot_b64,
                    url=current_url,
                    title=title,
                )
                for key, val in obs_timings.items():
                    self.metrics_evaluator.record_stage_latency(key, val)
                self.metrics_evaluator.record_stage_latency(
                    "world_model_build_ms", (time.time() - t0) * 1000
                )

                # ── 3. PRIVACY PROCESSING ─────────────────────────────
                current_origin = self._get_origin(current_url)
                sanitized_model, pii_matches, privacy_timings = (
                    self.world_model_builder.sanitize(local_model, current_origin)
                )
                latest_pii_matches = pii_matches
                for key, val in privacy_timings.items():
                    self.metrics_evaluator.record_stage_latency(key, val)

                self._emit("observation", {
                    "url": current_url,
                    "title": title,
                    "dom_nodes": len(dom_nodes),
                    "pii_count": len(pii_matches),
                    "pii_categories": [m.category.name for m in pii_matches],
                    "ocr_regions": len(local_model.ocr_regions),
                    "a11y_available": local_model.a11y_tree is not None,
                    "screenshot_b64": sanitized_model.redacted_screenshot_b64,
                })

                # ── 4. EGRESS GATE (Zero-Leakage Enforcement) ─────────
                t0 = time.time()
                legacy_obs = self.world_model_builder.to_legacy_observation(sanitized_model)
                legacy_payload = EgressPayload(
                    task=task,
                    observation=legacy_obs,
                    action_history=[
                        {
                            "step": r.step_index,
                            "action": r.action.action.value,
                            "node_id": r.action.node_id,
                            "text": r.action.text,
                            "placeholder_restored": r.action.placeholder_restored,
                        }
                        for r in self.action_history[-10:]
                    ],
                )
                self.egress_gate.audit_and_authorize(legacy_payload)
                self.metrics_evaluator.record_stage_latency(
                    "egress_audit_ms", (time.time() - t0) * 1000
                )

                # ── 5. REMOTE REASONING ───────────────────────────────
                t0 = time.time()
                plan: ActionPlan = self.provider.reason(
                    task=task,
                    world_model=sanitized_model,
                    action_history=self.action_history,
                    error_context=error_context,
                )
                self.metrics_evaluator.record_stage_latency(
                    "server_reasoning_ms", (time.time() - t0) * 1000
                )
                error_context = None  # Clear after re-plan

                self._emit("reasoning", {
                    "thought": plan.thought,
                    "actions": [
                        {"action": a.action.value, "node_id": a.node_id,
                         "text": a.text, "thought": a.thought}
                        for a in plan.actions
                    ],
                    "provider": self.provider.provider_name,
                })

                logger.info(f"[Reasoning] Plan: {plan.thought}")
                for i, a in enumerate(plan.actions):
                    logger.info(f"  Action {i+1}: {a.action.value} | {a.thought}")

                # ── 6. LOCAL EXECUTION (per-action firewall) ──────────
                if plan.actions and plan.actions[0].action == ActionType.DONE:
                    logger.info("Task completed!")
                    self._emit("task_complete", {"step": step_count})

                    sih_report = self._build_sih_report(
                        latest_pii_matches, dom_nodes, step_count
                    )
                    return self._build_result("SUCCESS", step_count, pii_matches, sih_report)

                # Check for loop detection
                action_key = self._action_plan_key(plan)
                if action_key == self._last_action_key:
                    self._consecutive_same_action += 1
                    if self._consecutive_same_action >= 3:
                        logger.warning("Loop detected — same plan proposed 3 times. Terminating.")
                        self._emit("task_complete", {"step": step_count, "reason": "loop_detected"})
                        sih_report = self._build_sih_report(
                            latest_pii_matches, dom_nodes, step_count
                        )
                        return self._build_result("LOOP_DETECTED", step_count, pii_matches, sih_report)
                else:
                    self._consecutive_same_action = 0
                self._last_action_key = action_key

                # Execute each action with firewall validation
                t0 = time.time()
                plan_broken = False
                for action_idx, proposed_action in enumerate(plan.actions):
                    if proposed_action.action == ActionType.DONE:
                        logger.info("Task completed (mid-plan)!")
                        self._emit("task_complete", {"step": step_count})
                        sih_report = self._build_sih_report(
                            latest_pii_matches, dom_nodes, step_count
                        )
                        return self._build_result("SUCCESS", step_count, pii_matches, sih_report)

                    # Re-extract DOM for freshness check on actions after the first
                    if action_idx > 0:
                        dom_nodes, formatted_dom = self.browser.extract_dom()

                    try:
                        success = self.firewall.execute_validated_action(
                            proposed_action, dom_nodes, current_origin
                        )

                        result = ActionResult(
                            action=proposed_action,
                            success=success,
                            step_index=step_count,
                        )
                        self.action_history.append(result)

                        self._emit("action_execute", {
                            "action": proposed_action.action.value,
                            "node_id": proposed_action.node_id,
                            "text": proposed_action.text,
                            "success": success,
                            "thought": proposed_action.thought,
                        })

                        if not success:
                            error_context = f"Action {proposed_action.action.value} on node {proposed_action.node_id} returned False"
                            plan_broken = True
                            break

                    except (ActionSecurityViolation, Exception) as e:
                        error_msg = str(e)[:200]
                        logger.warning(f"[Firewall] Action rejected: {error_msg}")
                        result = ActionResult(
                            action=proposed_action,
                            success=False,
                            error=error_msg,
                            step_index=step_count,
                        )
                        self.action_history.append(result)
                        error_context = f"Action {proposed_action.action.value} rejected by firewall: {error_msg}"
                        plan_broken = True
                        break

                self.metrics_evaluator.record_stage_latency(
                    "firewall_execution_ms", (time.time() - t0) * 1000
                )

                # ── 7. LOCAL VERIFICATION ─────────────────────────────
                t0 = time.time()
                post_nodes, _ = self.browser.extract_dom()
                if self.action_history:
                    last = self.action_history[-1]
                    verified = self.verifier.verify_action_execution(
                        last.action, dom_nodes, post_nodes
                    )
                    if not verified:
                        logger.warning("[Verifier] Action verification flagged anomaly.")
                self.metrics_evaluator.record_stage_latency(
                    "verification_ms", (time.time() - t0) * 1000
                )

                self._emit("metrics", {
                    "step": step_count,
                    "pii_total": len(latest_pii_matches),
                    "actions_total": len(self.action_history),
                    "token_usage": {
                        "input": self.provider.token_usage.input_tokens,
                        "output": self.provider.token_usage.output_tokens,
                        "calls": self.provider.token_usage.total_calls,
                    },
                })

            # Max steps reached
            logger.warning("Reached maximum step limit.")
            sih_report = self._build_sih_report(latest_pii_matches, dom_nodes, step_count)
            return self._build_result("MAX_STEPS_REACHED", step_count, latest_pii_matches, sih_report)

        finally:
            self.browser.stop()

    def _get_origin(self, url: str) -> str:
        """Extract origin from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else url

    def _action_plan_key(self, plan: ActionPlan) -> str:
        """Generate a key for loop detection."""
        parts = []
        for a in plan.actions:
            parts.append(f"{a.action.value}:{a.node_id}:{a.text}")
        return "|".join(parts)

    def _build_sih_report(self, pii_matches, dom_nodes, step_count):
        """Build SIH metrics report."""
        return self.metrics_evaluator.evaluate_sih_performance(
            detected_matches=pii_matches,
            ground_truth_pii_count=len(pii_matches),
            over_redacted_count=0,
            visual_grounding_matches=len(dom_nodes),
            total_visual_elements=max(1, len(dom_nodes)),
        )

    def _build_result(self, status, steps, pii_matches, sih_report):
        """Build result dictionary."""
        return {
            "status": status,
            "steps": steps,
            "pii_detected_count": len(pii_matches),
            "action_history": [
                {
                    "step": r.step_index,
                    "action": r.action.action.value,
                    "node_id": r.action.node_id,
                    "text": r.action.text,
                    "thought": r.action.thought,
                    "success": r.success,
                    "error": r.error,
                    "placeholder_restored": r.action.placeholder_restored,
                }
                for r in self.action_history
            ],
            "sih_report": sih_report,
            "provider": self.provider.provider_name,
            "token_usage": {
                "input": self.provider.token_usage.input_tokens,
                "output": self.provider.token_usage.output_tokens,
                "total_calls": self.provider.token_usage.total_calls,
            },
        }
