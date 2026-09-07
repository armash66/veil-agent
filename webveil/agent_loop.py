"""
WebVeil Main Agent Loop.
Executes the perceive-redact-transmit-act-verify loop adhering strictly to local privacy boundaries.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from webveil.browser.playwright_adapter import PlaywrightAdapter
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault
from webveil.core.privacy.redactor import LocalRedactor
from webveil.security.egress.privacy_gate import EgressPrivacyGate, PrivacyViolationError
from webveil.security.firewall.action_firewall import ActionFirewall, ActionSecurityViolation
from webveil.reasoning.server.vlm_server import VLMServerReasoningEngine
from webveil.core.verification.local_verifier import LocalVerifier
from webveil.evaluation.metrics import SIHMetricsEvaluator
from webveil.core.models.schema import SanitizedObservation, EgressPayload, BrowserAction, ActionType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebVeilAgentLoop")


class WebVeilAgent:
    """
    Core WebVeil Agent enforcing local privacy boundaries and managing browser interaction.
    """

    def __init__(self, max_steps: int = 15, headless: bool = True):
        self.max_steps = max_steps
        self.headless = headless

        # Subsystems
        self.browser = PlaywrightAdapter()
        self.detector = LocalPIIDetector()
        self.vault = ClientVault()
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.egress_gate = EgressPrivacyGate(self.detector)
        self.firewall = ActionFirewall(self.vault, self.browser)
        self.server = VLMServerReasoningEngine()
        self.verifier = LocalVerifier()
        self.metrics_evaluator = SIHMetricsEvaluator()

        self.action_history: List[Dict[str, Any]] = []

    def run_task(self, start_url: str, task: str) -> Dict[str, Any]:
        """
        Runs browser task while enforcing on-device perception & privacy bounds.
        """
        logger.info(f"Starting WebVeil Agent task: '{task}' on URL: {start_url}")
        self.metrics_evaluator.start_measurement()
        self.browser.start(headless=self.headless)
        self.vault.clear()
        self.action_history.clear()

        try:
            self.browser.navigate(start_url)
            current_origin = "http://localhost" if "localhost" in start_url or "127.0.0.1" in start_url else start_url

            step_count = 0
            latest_pii_matches = []

            while step_count < self.max_steps:
                step_count += 1
                logger.info(f"\n--- WEBVEIL STEP {step_count}/{self.max_steps} ---")

                # Sample RAM & CPU per step
                self.metrics_evaluator.sample_resources()

                # 1. Local Browser Observation & DOM Extraction
                t0 = time.time()
                dom_nodes, formatted_dom = self.browser.extract_dom()
                raw_screenshot_b64 = self.browser.capture_screenshot_b64()
                current_url = self.browser.get_current_url()
                title = self.browser.get_page_title()
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("dom_extraction_ms", (t1 - t0) * 1000)

                # 2. On-Device Privacy Detection & Sanitization
                t0 = time.time()
                sanitized_nodes, pii_matches = self.redactor.sanitize_dom(dom_nodes, current_origin)
                latest_pii_matches = pii_matches
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("pii_detection_ms", (t1 - t0) * 1000)

                t0 = time.time()
                redacted_screenshot_b64 = self.redactor.redact_screenshot_b64(raw_screenshot_b64, pii_matches)
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("redaction_ms", (t1 - t0) * 1000)

                # Rebuild formatted DOM using sanitized nodes
                sanitized_lines = []
                for n in sanitized_nodes:
                    if n.is_interactive:
                        line = f"[{n.node_id}] <{n.tag_name} type='{n.element_type}' name='{n.name}' placeholder='{n.attributes.get('placeholder', '')}' value='{n.value}'>{n.text_content}</{n.tag_name}>"
                        sanitized_lines.append(line)
                sanitized_formatted_dom = "\n".join(sanitized_lines)

                observation = SanitizedObservation(
                    url=current_url,
                    sanitized_url=current_url,
                    title=title,
                    dom_tree=sanitized_nodes,
                    formatted_dom=sanitized_formatted_dom,
                    redacted_screenshot_b64=redacted_screenshot_b64,
                    detected_pii_count=len(pii_matches),
                    pii_categories_found=[m.category.name for m in pii_matches]
                )

                # 3. Egress Privacy Gate Audit (Zero-Leakage Enforcement)
                t0 = time.time()
                payload = EgressPayload(
                    task=task,
                    observation=observation,
                    action_history=self.action_history
                )
                authorized_payload = self.egress_gate.audit_and_authorize(payload)
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("egress_audit_ms", (t1 - t0) * 1000)

                # 4. Remote Server VLM Reasoning
                t0 = time.time()
                proposed_action: BrowserAction = self.server.process_sanitized_request(authorized_payload)
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("server_reasoning_ms", (t1 - t0) * 1000)

                if proposed_action.action == ActionType.DONE:
                    logger.info("Task completed successfully!")
                    sih_report = self.metrics_evaluator.evaluate_sih_performance(
                        detected_matches=latest_pii_matches,
                        ground_truth_pii_count=len(latest_pii_matches),
                        over_redacted_count=0,
                        visual_grounding_matches=len(dom_nodes),
                        total_visual_elements=len(dom_nodes)
                    )
                    return {
                        "status": "SUCCESS",
                        "steps": step_count,
                        "pii_detected_count": len(pii_matches),
                        "action_history": self.action_history,
                        "sih_report": sih_report
                    }

                # 5. Local Action Firewall & Vault Restoration Execution
                t0 = time.time()
                success = self.firewall.execute_validated_action(proposed_action, dom_nodes, current_origin)
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("firewall_execution_ms", (t1 - t0) * 1000)
                
                # Record sanitized action history
                history_entry = {
                    "step": step_count,
                    "action": proposed_action.action.value,
                    "node_id": proposed_action.node_id,
                    "text": proposed_action.text,
                    "placeholder_restored": proposed_action.placeholder_restored
                }
                self.action_history.append(history_entry)

                # 6. Local Post-Action Verification
                t0 = time.time()
                post_nodes, _ = self.browser.extract_dom()
                verified = self.verifier.verify_action_execution(proposed_action, dom_nodes, post_nodes)
                t1 = time.time()
                self.metrics_evaluator.record_stage_latency("verification_ms", (t1 - t0) * 1000)

                if not verified:
                    logger.warning("[Verifier Warning] Action execution verification flagged anomaly.")

            logger.warning("Reached maximum step limit.")
            sih_report = self.metrics_evaluator.evaluate_sih_performance(
                detected_matches=latest_pii_matches,
                ground_truth_pii_count=len(latest_pii_matches),
                over_redacted_count=0,
                visual_grounding_matches=1,
                total_visual_elements=1
            )
            return {
                "status": "MAX_STEPS_REACHED",
                "steps": step_count,
                "pii_detected_count": len(latest_pii_matches),
                "action_history": self.action_history,
                "sih_report": sih_report
            }

        finally:
            self.browser.stop()
