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
from webveil.core.nlp.task_analyzer import TaskAnalyzer
from webveil.core.observation.dom_ranker import DOMRanker
from webveil.core.privacy.ner_detector import LocalPIINerEngine
from webveil.core.grounding.element_grounder import ElementGrounder
from webveil.core.models.schema import (
    ActionPlan, ActionResult, ActionType, BrowserAction,
    SanitizedObservation, EgressPayload, LocalWorldModel, SanitizedWorldModel,
    DOMRankingMetrics, GroundingResult, TaskRepresentation,
)
from webveil.core.models.state import AgentStage, AgentState, AgentEvent
from webveil.core.memory.working_memory import AgentWorkingMemory, FailureType
from webveil.core.context.manager import LocalContextManager
from webveil.browser.scheduler import ExecutionScheduler
from webveil.core.privacy.visual_privacy import VisualPrivacyEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebVeilAgent")


class WebVeilAgent:
    """
    Core WebVeil V1.5 Agent.
    Enforces: Local NLP → Local DOM Ranking → PII Risk Fusion → Sanitized Reasoning → Element Grounding → Action Firewall → Verification.
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
        self.task_analyzer = TaskAnalyzer()
        self.dom_ranker = DOMRanker()
        self.working_memory = AgentWorkingMemory()
        self.context_manager = LocalContextManager(self.dom_ranker)
        self.scheduler = ExecutionScheduler()
        self.visual_privacy = VisualPrivacyEngine()
        self.browser = PlaywrightAdapter()
        self.detector = LocalPIIDetector()
        self.ner_engine = LocalPIINerEngine(self.detector)
        self.vault = ClientVault()
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.world_model_builder = WorldModelBuilder(
            self.redactor, ocr_enabled=config.ocr_enabled
        )
        self.egress_gate = EgressPrivacyGate(self.detector)
        self.grounder = ElementGrounder()
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
            elif provider_name == "openrouter":
                provider_kwargs = {"api_key": config.openrouter_api_key, "model": config.openrouter_model}
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
        self.state: Optional[AgentState] = None

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

        # Stage 1: UNDERSTAND
        self.state = AgentState(task=task, max_steps=self.max_steps)
        self.state.stage = AgentStage.UNDERSTAND
        task_rep: TaskRepresentation = self.task_analyzer.analyze_task(task)

        # Working memory task registration & continuation preservation
        self.working_memory.set_task(task, task_rep)
        if self.working_memory.original_task and self.working_memory.original_task != task:
            logger.info(
                f"[AgentLoop] Preserving active persistent intent: '{self.working_memory.original_task}' "
                f"over continuation prompt '{task}'"
            )
            task = self.working_memory.original_task
            task_rep = self.working_memory.active_intent or task_rep

        self.state.task = task
        self.state.task_representation = task_rep

        understand_meta = {
            "intent": task_rep.intent,
            "entities": task_rep.entities,
            "constraints": task_rep.constraints,
            "count": task_rep.count,
            "objective": task_rep.objective,
            "confidence": task_rep.confidence,
        }
        self.state.emit_event(AgentStage.UNDERSTAND, "completed", understand_meta)
        self._emit("stage_change", {
            "stage": AgentStage.UNDERSTAND.value,
            "status": "completed",
            "data": understand_meta,
        })
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
                self.state.step_number = step_count
                logger.info(f"\n{'='*60}")
                logger.info(f"STEP {step_count}/{self.max_steps}")
                logger.info(f"{'='*60}")

                self.metrics_evaluator.sample_resources()
                self._emit("step_start", {"step": step_count, "max_steps": self.max_steps})

                # ── STAGE 2: OBSERVE (Local Multimodal Perception) ─────────
                self.state.stage = AgentStage.OBSERVE
                t0 = time.time()
                raw_dom_nodes, formatted_dom = self.browser.extract_dom()
                screenshot_b64 = self.browser.capture_screenshot_b64()
                current_url = self.browser.get_current_url()
                title = self.browser.get_page_title()
                self.state.current_url = current_url
                self.metrics_evaluator.record_stage_latency(
                    "dom_extraction_ms", (time.time() - t0) * 1000
                )

                # Build World Model
                t0 = time.time()
                local_model, obs_timings = self.world_model_builder.build_local_model(
                    page=self.browser.page,
                    dom_nodes=raw_dom_nodes,
                    formatted_dom=formatted_dom,
                    screenshot_b64=screenshot_b64,
                    url=current_url,
                    title=title,
                )
                self.state.observation = local_model
                for key, val in obs_timings.items():
                    self.metrics_evaluator.record_stage_latency(key, val)
                self.metrics_evaluator.record_stage_latency(
                    "world_model_build_ms", (time.time() - t0) * 1000
                )

                observe_meta = {
                    "url": current_url,
                    "title": title,
                    "raw_dom_nodes": len(raw_dom_nodes),
                    "ocr_regions": len(local_model.ocr_regions),
                    "has_a11y": local_model.a11y_tree is not None,
                    "has_screenshot": bool(screenshot_b64),
                }
                self.state.emit_event(AgentStage.OBSERVE, "completed", observe_meta)
                self._emit("stage_change", {"stage": AgentStage.OBSERVE.value, "status": "completed", "data": observe_meta})

                # ── STAGE 3: FILTER (Task-Aware DOM Intelligence) ──────────
                self.state.stage = AgentStage.FILTER
                ranked_nodes, ranking_metrics = self.dom_ranker.rank_and_compress(raw_dom_nodes, task_rep)
                self.state.selected_elements = ranked_nodes
                filter_meta = {
                    "raw_nodes": ranking_metrics.raw_nodes,
                    "filtered_nodes": ranking_metrics.filtered_nodes,
                    "compression_ratio": ranking_metrics.compression_ratio,
                    "tokens_saved": ranking_metrics.estimated_tokens_saved,
                }
                self.state.emit_event(AgentStage.FILTER, "completed", filter_meta)
                self._emit("stage_change", {"stage": AgentStage.FILTER.value, "status": "completed", "data": filter_meta})

                # Attach filtered nodes to local model
                local_model.dom_nodes = ranked_nodes

                # ── STAGE 4: PROTECT (Privacy Engine & Risk Fusion) ────────
                self.state.stage = AgentStage.PROTECT
                current_origin = self._get_origin(current_url)
                sanitized_model, pii_matches, privacy_timings = (
                    self.world_model_builder.sanitize(local_model, current_origin)
                )
                self.state.sanitized_observation = sanitized_model
                self.state.privacy_results = pii_matches
                latest_pii_matches = pii_matches
                for key, val in privacy_timings.items():
                    self.metrics_evaluator.record_stage_latency(key, val)

                protect_meta = {
                    "pii_detected": len(pii_matches),
                    "tokens_created": len(pii_matches),
                    "categories": [m.category.name for m in pii_matches],
                }
                self.state.emit_event(AgentStage.PROTECT, "completed", protect_meta)
                self._emit("stage_change", {"stage": AgentStage.PROTECT.value, "status": "completed", "data": protect_meta})

                self._emit("observation", {
                    "url": current_url,
                    "title": title,
                    "raw_dom_nodes": ranking_metrics.raw_nodes,
                    "dom_nodes": ranking_metrics.filtered_nodes,
                    "compression_ratio": ranking_metrics.compression_ratio,
                    "tokens_saved": ranking_metrics.estimated_tokens_saved,
                    "pii_count": len(pii_matches),
                    "pii_categories": [m.category.name for m in pii_matches],
                    "ocr_regions": len(local_model.ocr_regions),
                    "a11y_available": local_model.a11y_tree is not None,
                    "screenshot_b64": sanitized_model.redacted_screenshot_b64,
                })

                # Egress Gate (Zero-Leakage Audit)
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

                # ── STAGE 5: REASON (Remote LLM Action Proposal) ───────────
                self.state.stage = AgentStage.REASON
                t0 = time.time()
                plan: ActionPlan = self.provider.reason(
                    task=task,
                    world_model=sanitized_model,
                    action_history=self.action_history,
                    error_context=error_context,
                )
                self.state.reasoning_result = plan
                self.state.proposed_actions = list(plan.actions)
                self.metrics_evaluator.record_stage_latency(
                    "server_reasoning_ms", (time.time() - t0) * 1000
                )
                error_context = None  # Clear after re-plan

                reason_meta = {
                    "actions_proposed": len(plan.actions),
                    "thought": plan.thought[:150] if plan.thought else "",
                    "provider": self.provider.provider_name,
                }
                self.state.emit_event(AgentStage.REASON, "completed", reason_meta)
                self._emit("stage_change", {"stage": AgentStage.REASON.value, "status": "completed", "data": reason_meta})

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

                if plan.actions and plan.actions[0].action == ActionType.DONE:
                    logger.info("Task completed!")
                    self.state.stage = AgentStage.DONE
                    self.state.termination_reason = "SUCCESS"
                    self.state.emit_event(AgentStage.DONE, "completed", {"step": step_count, "reason": "SUCCESS"})
                    self._emit("task_complete", {"step": step_count, "reason": "SUCCESS"})

                    sih_report = self._build_sih_report(
                        latest_pii_matches, raw_dom_nodes, step_count
                    )
                    return self._build_result("SUCCESS", step_count, pii_matches, sih_report)

                # Loop Detection Check
                action_key = self._action_plan_key(plan)
                if action_key == self._last_action_key:
                    self._consecutive_same_action += 1
                    if self._consecutive_same_action >= 3:
                        logger.warning("Loop detected — same plan proposed 3 times. Terminating.")
                        self.state.stage = AgentStage.DONE
                        self.state.termination_reason = "LOOP_DETECTED"
                        self.state.emit_event(AgentStage.DONE, "completed", {"step": step_count, "reason": "LOOP_DETECTED"})
                        self._emit("task_complete", {"step": step_count, "reason": "loop_detected"})
                        sih_report = self._build_sih_report(
                            latest_pii_matches, raw_dom_nodes, step_count
                        )
                        return self._build_result("LOOP_DETECTED", step_count, pii_matches, sih_report)
                else:
                    self._consecutive_same_action = 0
                self._last_action_key = action_key

                # Execute actions: GROUND → AUTHORIZE → ACT → VERIFY
                t0 = time.time()
                for action_idx, proposed_action in enumerate(plan.actions):
                    if proposed_action.action == ActionType.DONE:
                        logger.info("Task completed (mid-plan)!")
                        self.state.stage = AgentStage.DONE
                        self.state.termination_reason = "SUCCESS"
                        self.state.emit_event(AgentStage.DONE, "completed", {"step": step_count, "reason": "SUCCESS"})
                        self._emit("task_complete", {"step": step_count, "reason": "SUCCESS"})
                        sih_report = self._build_sih_report(
                            latest_pii_matches, raw_dom_nodes, step_count
                        )
                        return self._build_result("SUCCESS", step_count, pii_matches, sih_report)

                    if action_idx > 0:
                        raw_dom_nodes, formatted_dom = self.browser.extract_dom()

                    # ── STAGE 6: GROUND (Element Grounding Engine) ─────────
                    self.state.stage = AgentStage.GROUND
                    grounding: GroundingResult = self.grounder.ground_action(proposed_action, raw_dom_nodes)
                    ground_meta = {
                        "action": proposed_action.action.value,
                        "node_id": proposed_action.node_id,
                        "confidence": grounding.confidence,
                        "threshold_action": grounding.threshold_action,
                    }
                    self.state.emit_event(
                        AgentStage.GROUND,
                        "completed" if grounding.threshold_action != "REPLAN" else "failed",
                        ground_meta
                    )
                    self._emit("stage_change", {"stage": AgentStage.GROUND.value, "status": "completed", "data": ground_meta})

                    if grounding.threshold_action == "REPLAN":
                        logger.warning(f"[Grounding REJECT] Low confidence ({grounding.confidence}). Requesting REPLAN.")
                        self.state.stage = AgentStage.REPLAN
                        self.state.emit_event(AgentStage.REPLAN, "started", {"reason": grounding.reasoning})
                        self._emit("stage_change", {"stage": AgentStage.REPLAN.value, "data": {"reason": grounding.reasoning}})
                        error_context = f"Grounding failed: {grounding.reasoning}"
                        break

                    # ── STAGE 7: AUTHORIZE (Action Schema & Policy Validation) ──
                    self.state.stage = AgentStage.AUTHORIZE
                    try:
                        self.firewall.validate_action_schema(proposed_action)
                        auth_meta = {"action": proposed_action.action.value, "node_id": proposed_action.node_id}
                        self.state.emit_event(AgentStage.AUTHORIZE, "completed", auth_meta)
                        self._emit("stage_change", {"stage": AgentStage.AUTHORIZE.value, "status": "completed", "data": auth_meta})
                    except Exception as auth_err:
                        auth_err_msg = str(auth_err)[:200]
                        logger.warning(f"[Authorization Reject] {auth_err_msg}")
                        self.state.emit_event(AgentStage.AUTHORIZE, "blocked", {"error": auth_err_msg})
                        fail_result = ActionResult(
                            action=proposed_action,
                            success=False,
                            error=auth_err_msg,
                            step_index=step_count,
                        )
                        self.state.failed_actions.append(fail_result)
                        self.action_history.append(fail_result)
                        error_context = f"Action {proposed_action.action.value} authorization blocked: {auth_err_msg}"
                        break

                    # ── STAGE 8: ACT (Action Execution & Secret Restoration) ───
                    self.state.stage = AgentStage.ACT
                    act_meta = {"action": proposed_action.action.value, "node_id": proposed_action.node_id}
                    self._emit("stage_change", {"stage": AgentStage.ACT.value, "data": act_meta})
                    try:
                        # ── Execution Readiness (ExecutionScheduler) ──
                        readiness = self.scheduler.await_readiness(
                            self.browser.page, proposed_action
                        )
                        if not readiness.is_ready:
                            logger.warning(f"[Scheduler] Readiness warning: {readiness.reason}")

                        success = self.firewall.execute_validated_action(
                            proposed_action, raw_dom_nodes, current_origin
                        )

                        result = ActionResult(
                            action=proposed_action,
                            success=success,
                            step_index=step_count,
                        )
                        if success:
                            self.state.executed_actions.append(result)
                        else:
                            self.state.failed_actions.append(result)
                            self.working_memory.record_failure(
                                FailureType.STALE_TARGET,
                                step_count,
                                f"Action {proposed_action.action.value} execution returned False",
                                proposed_action
                            )
                        self.action_history.append(result)
                        self.working_memory.record_action(
                            action=proposed_action,
                            success=success,
                            step_index=step_count,
                        )

                        self.state.emit_event(AgentStage.ACT, "completed" if success else "failed", {
                            "action": proposed_action.action.value,
                            "node_id": proposed_action.node_id,
                            "success": success,
                        })

                        self._emit("action_execute", {
                            "action": proposed_action.action.value,
                            "node_id": proposed_action.node_id,
                            "text": proposed_action.text,
                            "success": success,
                            "thought": proposed_action.thought,
                            "confidence": grounding.confidence,
                        })

                        if not success:
                            error_context = f"Action {proposed_action.action.value} on node {proposed_action.node_id} returned False"
                            break

                    except (ActionSecurityViolation, Exception) as e:
                        error_msg = str(e)[:200]
                        logger.warning(f"[Firewall] Action rejected: {error_msg}")
                        fail_type = FailureType.FIREWALL_REJECTION if isinstance(e, ActionSecurityViolation) else FailureType.STALE_TARGET
                        self.working_memory.record_failure(fail_type, step_count, error_msg, proposed_action)
                        result = ActionResult(
                            action=proposed_action,
                            success=False,
                            error=error_msg,
                            step_index=step_count,
                        )
                        self.state.failed_actions.append(result)
                        self.action_history.append(result)
                        self.state.emit_event(AgentStage.ACT, "failed", {
                            "action": proposed_action.action.value,
                            "error": error_msg,
                        })
                        error_context = f"Action {proposed_action.action.value} rejected by firewall: {error_msg}"
                        break

                self.metrics_evaluator.record_stage_latency(
                    "firewall_execution_ms", (time.time() - t0) * 1000
                )

                # ── STAGE 9: VERIFY (Local Post-Action Verification) ───────
                self.state.stage = AgentStage.VERIFY
                t0 = time.time()
                post_nodes, _ = self.browser.extract_dom()
                verified = True
                if self.action_history:
                    last = self.action_history[-1]
                    if hasattr(self.verifier, "verify_action_result"):
                        v_res = self.verifier.verify_action_result(
                            last.action, raw_dom_nodes, post_nodes,
                            current_url=current_url, user_task=task
                        )
                        verified = (v_res.status.value == "SUCCESS")
                        if not verified:
                            all_reasons = list(v_res.reasons)
                            if v_res.detected_errors:
                                all_reasons.extend(v_res.detected_errors)
                            reasons_str = "; ".join(all_reasons) or "State mutation anomaly"
                            logger.warning(f"[Verifier] Action verification flagged anomaly: {reasons_str}")
                            error_context = f"Verification failed for action {last.action.action.value}: {reasons_str}"
                            self.state.stage = AgentStage.REPLAN
                            self.state.emit_event(AgentStage.REPLAN, "started", {"reason": error_context})
                            self._emit("stage_change", {"stage": AgentStage.REPLAN.value, "data": {"reason": error_context}})
                    else:
                        verified = self.verifier.verify_action_execution(
                            last.action, raw_dom_nodes, post_nodes
                        )
                        if not verified:
                            logger.warning("[Verifier] Action verification flagged anomaly.")
                            error_context = f"Verification failed for action {last.action.action.value}"
                            self.state.stage = AgentStage.REPLAN
                            self.state.emit_event(AgentStage.REPLAN, "started", {"reason": error_context})
                            self._emit("stage_change", {"stage": AgentStage.REPLAN.value, "data": {"reason": error_context}})

                    if verified:
                        self.working_memory.advance_goal_on_success()
                    else:
                        self.working_memory.record_failure(
                            FailureType.VERIFICATION_FAILURE,
                            step_count,
                            error_context or "Verification anomaly",
                            last.action if self.action_history else None,
                        )
                self.state.verification_result = verified
                self.state.emit_event(AgentStage.VERIFY, "completed" if verified else "failed", {"verified": verified})
                self._emit("stage_change", {"stage": AgentStage.VERIFY.value, "data": {"step": step_count, "verified": verified}})
                self.metrics_evaluator.record_stage_latency(
                    "verification_ms", (time.time() - t0) * 1000
                )

                # ── STAGE 10: UPDATE_STATE (State Synchronization) ────────
                self.state.stage = AgentStage.UPDATE_STATE
                state_update_meta = {
                    "step": step_count,
                    "executed_actions": len(self.state.executed_actions),
                    "failed_actions": len(self.state.failed_actions),
                    "pii_total": len(latest_pii_matches),
                }
                self.state.emit_event(AgentStage.UPDATE_STATE, "completed", state_update_meta)
                self._emit("stage_change", {"stage": AgentStage.UPDATE_STATE.value, "data": state_update_meta})

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
            self.state.stage = AgentStage.DONE
            self.state.termination_reason = "MAX_STEPS_REACHED"
            self.state.emit_event(AgentStage.DONE, "completed", {"step": step_count, "reason": "MAX_STEPS_REACHED"})
            sih_report = self._build_sih_report(latest_pii_matches, self.state.selected_elements or raw_dom_nodes, step_count)
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
        if hasattr(self, "state") and self.state:
            self.state.termination_reason = status
        return {
            "status": status,
            "steps": steps,
            "pii_detected_count": len(pii_matches),
            "state": self.state,
            "events": [e.to_dict() for e in self.state.events] if (hasattr(self, "state") and self.state) else [],
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
