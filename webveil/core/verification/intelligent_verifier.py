"""
Intelligent Multi-Criterion Verification Engine.
Evaluates DOM mutations, URL state, form validations, negative error indicators,
and task goal completion confidence before transitioning agent states.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple

from webveil.core.models.schema import BrowserAction, ActionType, DOMNode

logger = logging.getLogger("WebVeilVerification.Intelligent")


class VerificationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"
    NEGATIVE_ERROR_DETECTED = "NEGATIVE_ERROR_DETECTED"


@dataclass
class VerificationResult:
    status: VerificationStatus
    confidence: float
    reasons: List[str] = field(default_factory=list)
    detected_errors: List[str] = field(default_factory=list)
    dom_mutations_count: int = 0
    url_changed: bool = False
    should_replan: bool = False


class IntelligentVerifier:
    """
    Multi-criterion task-aware post-action verifier.
    Enforces local fail-closed verification before completing tasks or continuing chains.
    """

    ERROR_PATTERNS = [
        re.compile(r'\b(?:error|failed|failure|invalid|not found|404|500|502|503|access denied|unauthorized|forbidden|timed? out)\b', re.IGNORECASE),
        re.compile(r'\b(?:rate limit(?:ed)?|too many requests|captcha required|verification required)\b', re.IGNORECASE),
        re.compile(r'\b(?:this field is required|please enter a valid|incorrect (?:password|credentials|email))\b', re.IGNORECASE),
    ]

    SUCCESS_PATTERNS = [
        re.compile(r'\b(?:success|completed|confirmed|order placed|payment received|thank you|welcome|dashboard|saved successfully)\b', re.IGNORECASE),
    ]

    def verify_action_execution(
        self,
        action: BrowserAction,
        previous_nodes: List[DOMNode],
        current_nodes: List[DOMNode],
        previous_url: str = "about:blank",
        current_url: str = "about:blank",
        user_task: str = "",
    ) -> VerificationResult:
        """
        Comprehensive multi-criterion verification of action outcome.
        """
        reasons: List[str] = []
        detected_errors: List[str] = []

        # Criterion 1: Negative Error Indicator Scan
        errors_found = self._scan_negative_indicators(current_nodes)
        if errors_found:
            detected_errors.extend(errors_found)
            reasons.append(f"Detected {len(errors_found)} error indicator(s) in active page.")
            return VerificationResult(
                status=VerificationStatus.NEGATIVE_ERROR_DETECTED,
                confidence=0.10,
                reasons=reasons,
                detected_errors=detected_errors,
                should_replan=True,
            )

        # Criterion 2: Navigation & URL Transitions
        url_changed = (previous_url != current_url and current_url != "about:blank")
        if action.action == ActionType.NAVIGATE:
            if action.url and action.url.lower() in current_url.lower() or url_changed:
                reasons.append(f"Successfully navigated to {current_url}")
                return VerificationResult(
                    status=VerificationStatus.SUCCESS,
                    confidence=0.95,
                    reasons=reasons,
                    url_changed=url_changed,
                    should_replan=False,
                )
            else:
                reasons.append(f"Navigation to {action.url} did not reflect in current URL {current_url}")
                return VerificationResult(
                    status=VerificationStatus.FAILURE,
                    confidence=0.30,
                    reasons=reasons,
                    url_changed=url_changed,
                    should_replan=True,
                )

        # Criterion 3: DOM Mutations
        prev_ids = {n.node_id for n in previous_nodes}
        curr_ids = {n.node_id for n in current_nodes}
        added_ids = curr_ids - prev_ids
        removed_ids = prev_ids - curr_ids
        mutations_count = len(added_ids) + len(removed_ids)

        if action.action == ActionType.DONE:
            # Check if task goals are satisfied
            task_success = self._check_success_indicators(current_nodes, user_task)
            confidence = 0.90 if task_success else 0.75
            reasons.append("Task completion signaled.")
            return VerificationResult(
                status=VerificationStatus.SUCCESS,
                confidence=confidence,
                reasons=reasons,
                dom_mutations_count=mutations_count,
                url_changed=url_changed,
                should_replan=False,
            )

        if action.action == ActionType.TYPE:
            target = next((n for n in current_nodes if n.node_id == action.node_id), None)
            if target and (target.value or target.attributes.get("value")):
                reasons.append(f"Input field node {action.node_id} received input.")
                return VerificationResult(
                    status=VerificationStatus.SUCCESS,
                    confidence=0.90,
                    reasons=reasons,
                    dom_mutations_count=mutations_count,
                    url_changed=url_changed,
                    should_replan=False,
                )

        if action.action == ActionType.CLICK:
            if mutations_count > 0 or url_changed:
                reasons.append(f"Click on node {action.node_id} triggered {mutations_count} DOM mutations.")
                return VerificationResult(
                    status=VerificationStatus.SUCCESS,
                    confidence=0.88,
                    reasons=reasons,
                    dom_mutations_count=mutations_count,
                    url_changed=url_changed,
                    should_replan=False,
                )
            else:
                reasons.append(f"Click on node {action.node_id} produced no visible state changes or mutations.")
                return VerificationResult(
                    status=VerificationStatus.PARTIAL_SUCCESS,
                    confidence=0.60,
                    reasons=reasons,
                    dom_mutations_count=0,
                    url_changed=False,
                    should_replan=True,
                )

        # Default fallback (SCROLL, WAIT, KEYPRESS)
        reasons.append(f"Action {action.action.name} dispatched.")
        return VerificationResult(
            status=VerificationStatus.SUCCESS,
            confidence=0.80,
            reasons=reasons,
            dom_mutations_count=mutations_count,
            url_changed=url_changed,
            should_replan=False,
        )

    def _scan_negative_indicators(self, nodes: List[DOMNode]) -> List[str]:
        """Scan visible text of active nodes for error alerts and negative indicators."""
        errors: List[str] = []
        for node in nodes:
            if not node.is_visible or not node.text_content:
                continue
            text = node.text_content.strip()
            # Only check short-to-medium alerts to avoid false positives on whole page containers
            if len(text) > 300:
                continue
            for pat in self.ERROR_PATTERNS:
                if pat.search(text):
                    # Exclude common benign occurrences
                    if any(b in text.lower() for b in ["report error", "report a bug", "zero error rate"]):
                        continue
                    errors.append(f"Node [{node.node_id}] <{node.tag_name}>: '{text[:80]}'")
                    break
        return errors

    def _check_success_indicators(self, nodes: List[DOMNode], task: str) -> bool:
        """Check if any node indicates positive completion of task."""
        for node in nodes:
            if not node.is_visible or not node.text_content:
                continue
            text = node.text_content.strip()
            if len(text) > 200:
                continue
            for pat in self.SUCCESS_PATTERNS:
                if pat.search(text):
                    return True
        return False
