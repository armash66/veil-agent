"""
Egress Guard & Mandatory Sanitization Enforcer.
Provides a strict single-choke-point wrapper around image egress.
Fails CLOSED on error, and performs secondary assertion scanning on output buffers.
"""

import base64
import io
import logging
from typing import List, Optional
from PIL import Image, ImageDraw
from webveil.core.models.schema import PIIMatch
from webveil.core.privacy.redactor import LocalRedactor

logger = logging.getLogger("WebVeilEgressGuard")


class EgressViolationError(Exception):
    """Raised when screenshot egress fails sanitization, OCR detection, or verification checks."""
    pass


class EgressGuard:
    """
    Single hard choke-point for any outgoing screenshot / visual payload.
    Enforces fail-closed semantics and post-redaction verification.
    """

    def __init__(self, redactor: LocalRedactor, ocr_detector_func, canary_strings: Optional[List[str]] = None):
        if ocr_detector_func is None:
            raise ValueError("EgressGuard requires a non-None ocr_detector_func dependency. Fail-open uninspected egress is prohibited.")
        self.redactor = redactor
        self.ocr_detector_func = ocr_detector_func
        self.canary_strings = canary_strings or []

    def sanitize_screenshot_for_egress(
        self,
        raw_b64: str,
        matches: List[PIIMatch]
    ) -> str:
        """
        Processes a raw base64 screenshot for network transmission.

        Guarantees:
        1. Fail-closed: Any exception, missing image, or OCR failure blocks egress by raising EgressViolationError.
        2. Visual Masking: Applies solid redaction boxes over all matched PII bounding boxes (with padding).
        3. Pixel Verification: Re-runs OCR detector on output image buffer to verify zero PII text remains visible in rendered pixels.
        """
        if not raw_b64:
            raise EgressViolationError("Egress blocked: Empty screenshot payload provided.")

        try:
            # Validate decode
            img_bytes = base64.b64decode(raw_b64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            logger.critical(f"[EGRESS GUARD FAIL-CLOSED] Invalid image buffer provided: {e}")
            raise EgressViolationError(f"Egress blocked: Unable to parse raw image payload. Error: {e}")

        # Mandatory OCR Execution
        all_matches = list(matches)
        try:
            ocr_matches = self.ocr_detector_func(image)
            if ocr_matches:
                all_matches.extend(ocr_matches)
        except Exception as ocr_err:
            logger.critical(f"[EGRESS GUARD FAIL-CLOSED] OCR engine error: {ocr_err}")
            raise EgressViolationError(f"Egress blocked: OCR detection engine failed: {ocr_err}")

        # Perform Redaction
        try:
            if all_matches:
                redacted_b64 = self.redactor.redact_screenshot_b64(raw_b64, all_matches)
            else:
                redacted_b64 = raw_b64
        except Exception as redact_err:
            logger.critical(f"[EGRESS GUARD FAIL-CLOSED] Redaction engine error: {redact_err}")
            raise EgressViolationError(f"Egress blocked: Redaction processing failed: {redact_err}")

        # Post-redaction Verification Check on rendered PIXELS via OCR
        self._assert_pixel_verification(redacted_b64, all_matches)

        return redacted_b64

    def _assert_pixel_verification(self, redacted_b64: str, original_matches: List[PIIMatch]):
        """
        Re-decodes output image and re-runs OCR over output pixels to assert zero PII remains visible.
        """
        try:
            redacted_bytes = base64.b64decode(redacted_b64)
            output_image = Image.open(io.BytesIO(redacted_bytes)).convert("RGB")
            
            # Re-run OCR on output image
            post_ocr_matches = self.ocr_detector_func(output_image)
            
            raw_secrets = {m.raw_value for m in original_matches if m.raw_value}
            forbidden_set = raw_secrets.union(set(self.canary_strings))

            if post_ocr_matches:
                for match in post_ocr_matches:
                    for forbidden in forbidden_set:
                        if forbidden in match.raw_value or match.raw_value in forbidden:
                            logger.critical(f"[EGRESS VIOLATION] Rendered pixel PII leak detected after redaction: '{match.raw_value}'")
                            raise EgressViolationError(f"Security invariant violated: OCR detected unredacted PII text '{match.raw_value}' in output pixels.")

            # Secondary raw metadata byte check
            for secret in forbidden_set:
                if len(secret) > 3 and secret.encode('utf-8') in redacted_bytes:
                    logger.critical(f"[EGRESS VIOLATION] Raw secret metadata byte leak detected in output buffer!")
                    raise EgressViolationError("Security invariant violated: Secret byte string detected in output buffer metadata.")

        except EgressViolationError:
            raise
        except Exception as err:
            logger.critical(f"[EGRESS GUARD FAIL-CLOSED] Post-verification pixel scan failed: {err}")
            raise EgressViolationError(f"Egress blocked: Post-redaction verification failed: {err}")
