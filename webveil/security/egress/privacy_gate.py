"""
Egress Privacy Gate.
Final line of defense enforcing zero-leakage invariant before network transmission.
"""

import json
import logging
from typing import Any, Dict
from webveil.core.models.schema import EgressPayload, SanitizedObservation
from webveil.core.privacy.pii_detector import LocalPIIDetector

logger = logging.getLogger("WebVeilEgressGate")


class PrivacyViolationError(Exception):
    """Raised when unredacted PII or synthetic canary is detected in egress network payload."""
    pass


class EgressPrivacyGate:
    """
    Hard enforcement boundary inspecting all outgoing payloads before network request.
    """

    def __init__(self, detector: LocalPIIDetector):
        self.detector = detector

    def audit_and_authorize(self, payload: EgressPayload) -> Dict[str, Any]:
        """
        Inspects payload for raw PII leakage. Raises PrivacyViolationError if audit fails.
        """
        # Convert observation and action history to serializable dict
        serialized_payload = {
            "task": payload.task,
            "url": payload.observation.sanitized_url,
            "title": payload.observation.title,
            "dom": payload.observation.formatted_dom,
            "has_screenshot": bool(payload.observation.redacted_screenshot_b64),
            "pii_detected_count": payload.observation.detected_pii_count,
            "pii_categories": payload.observation.pii_categories_found,
            "action_history": payload.action_history
        }

        json_str = json.dumps(serialized_payload)

        # 1. Audit for synthetic canary strings
        canary_matches = list(self.detector.CANARY_REGEX.finditer(json_str))
        if canary_matches:
            found_canaries = [m.group(0) for m in canary_matches]
            logger.critical(f"[PRIVACY VIOLATION] Raw canary strings detected in egress payload: {found_canaries}")
            raise PrivacyViolationError(f"Egress payload blocked! Raw canary strings detected: {found_canaries}")

        # 2. Audit for raw Aadhaar patterns
        aadhaar_matches = list(self.detector.AADHAAR_REGEX.finditer(json_str))
        if aadhaar_matches:
            logger.critical("[PRIVACY VIOLATION] Unredacted Aadhaar number detected in egress payload!")
            raise PrivacyViolationError("Egress payload blocked! Unredacted Aadhaar number detected in payload")

        # 3. Audit for raw Email patterns
        email_matches = list(self.detector.EMAIL_REGEX.finditer(json_str))
        if email_matches:
            logger.critical("[PRIVACY VIOLATION] Unredacted Email address detected in egress payload!")
            raise PrivacyViolationError("Egress payload blocked! Unredacted Email address detected in payload")

        # 4. Audit for raw Phone patterns
        phone_matches = list(self.detector.PHONE_REGEX.finditer(json_str))
        if phone_matches:
            logger.critical("[PRIVACY VIOLATION] Unredacted Phone number detected in egress payload!")
            raise PrivacyViolationError("Egress payload blocked! Unredacted Phone number detected in payload")

        logger.info(f"[Egress Gate AUTHORIZED] Zero canary leakage verified for URL {payload.observation.sanitized_url}")
        
        # Include redacted screenshot if present
        if payload.observation.redacted_screenshot_b64:
            serialized_payload["screenshot_b64"] = payload.observation.redacted_screenshot_b64

        return serialized_payload
