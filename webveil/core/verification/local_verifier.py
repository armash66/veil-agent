"""
Local Post-Action Verifier.
Verifies browser execution results locally without sending raw DOM to server.
"""

import logging
from typing import List, Optional
from webveil.core.models.schema import BrowserAction, ActionType, DOMNode
from webveil.core.verification.intelligent_verifier import IntelligentVerifier, VerificationResult, VerificationStatus

logger = logging.getLogger("WebVeilLocalVerifier")


class LocalVerifier:
    """
    On-device post-action verification engine backed by IntelligentVerifier.
    """

    def __init__(self):
        self.intelligent_verifier = IntelligentVerifier()

    def verify_action_execution(
        self,
        action: BrowserAction,
        previous_nodes: List[DOMNode],
        current_nodes: List[DOMNode],
        previous_url: str = "about:blank",
        current_url: str = "about:blank",
        user_task: str = "",
    ) -> bool:
        """
        Verifies if proposed action successfully transformed DOM state as expected.
        Returns True if verified or acceptable, False if hard error detected or failure.
        """
        result = self.intelligent_verifier.verify_action_execution(
            action=action,
            previous_nodes=previous_nodes,
            current_nodes=current_nodes,
            previous_url=previous_url,
            current_url=current_url,
            user_task=user_task,
        )
        if result.status == VerificationStatus.NEGATIVE_ERROR_DETECTED:
            logger.warning(f"[LocalVerifier REJECT] Negative error indicators detected: {result.detected_errors}")
            return False

        if result.status == VerificationStatus.FAILURE:
            logger.warning(f"[LocalVerifier FAIL] Action outcome failed verification: {result.reasons}")
            return False

        return True

    def verify_action_result(
        self,
        action: BrowserAction,
        previous_nodes: List[DOMNode],
        current_nodes: List[DOMNode],
        previous_url: str = "about:blank",
        current_url: str = "about:blank",
        user_task: str = "",
    ) -> VerificationResult:
        """
        Comprehensive evaluation returning complete VerificationResult dataclass.
        """
        return self.intelligent_verifier.verify_action_execution(
            action=action,
            previous_nodes=previous_nodes,
            current_nodes=current_nodes,
            previous_url=previous_url,
            current_url=current_url,
            user_task=user_task,
        )
