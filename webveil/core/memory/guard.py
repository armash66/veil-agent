"""
Zero-PII Memory Guard.
Authoritative gate checking that no raw secrets, credentials, or PII
are ever committed to long-term agent episodic or site memory stores.
"""

import logging
from typing import List, Optional
from webveil.core.privacy.pii_detector import LocalPIIDetector

logger = logging.getLogger("WebVeilMemory.Guard")


class MemoryPrivacyViolation(Exception):
    """Raised when an entry intended for long-term memory contains unredacted PII."""
    pass


class ZeroPIIMemoryGuard:
    """
    Enforces privacy invariants on all agent memory entries before persistence.
    """

    def __init__(self, detector: Optional[LocalPIIDetector] = None):
        self.detector = detector or LocalPIIDetector()

    def assert_clean(self, text: str, context: str = "memory"):
        """Scan text and assert that zero PII matches are detected."""
        if not text:
            return

        matches = self.detector.scan_text(text)
        if matches:
            categories = [m.category.value for m in matches]
            logger.critical(
                f"[MEMORY PRIVACY VIOLATION] Attempted to store unredacted PII in {context}: {categories}"
            )
            raise MemoryPrivacyViolation(
                f"Memory write rejected: text contains unredacted PII categories {categories}"
            )
