"""
Visual Privacy & Sensitive Region Redactor.
Identifies visual sensitive candidate regions (identity cards, payment cards,
QR codes, signatures, profile accounts) from local visual perception and applies solid blackout redaction.
Enforces the fail-closed invariant: raw visual sensitive regions NEVER leave the client.
"""

import io
import base64
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw

from webveil.core.models.schema import VisualRegion, TextRegion

logger = logging.getLogger("WebVeilPrivacy.VisualPrivacy")


class VisualSensitiveCategory(str, Enum):
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    PAYMENT_CARD = "PAYMENT_CARD"
    QR_BARCODE = "QR_BARCODE"
    SIGNATURE = "SIGNATURE"
    PRIVATE_PROFILE = "PRIVATE_PROFILE"
    CONFIDENTIAL_NOTICE = "CONFIDENTIAL_NOTICE"


@dataclass
class VisualRedactionRecord:
    redaction_id: str
    category: VisualSensitiveCategory
    bounding_box: Dict[str, float]  # {x, y, width, height}
    confidence: float
    source: str
    policy_decision: str = "BLOCK"  # "BLOCK" | "TOKENIZE" | "LOCAL_ONLY"


class VisualPrivacyEngine:
    """
    On-device visual sensitive region classifier and canvas redaction engine.
    """

    SENSITIVE_KEYWORDS = {
        VisualSensitiveCategory.IDENTITY_DOCUMENT: ["aadhaar", "passport", "driving license", "pan card", "ssn", "voter id"],
        VisualSensitiveCategory.PAYMENT_CARD: ["cvv", "valid thru", "card number", "debit card", "credit card", "mastercard", "visa"],
        VisualSensitiveCategory.QR_BARCODE: ["scan qr", "upi qr", "qr code", "barcode"],
        VisualSensitiveCategory.SIGNATURE: ["signature", "sign here", "authorized signatory"],
        VisualSensitiveCategory.CONFIDENTIAL_NOTICE: ["confidential", "internal only", "do not disclose", "restricted access"],
    }

    def detect_and_redact(
        self,
        screenshot_b64: str,
        visual_regions: List[VisualRegion],
        ocr_regions: List[TextRegion],
    ) -> Tuple[str, List[VisualRedactionRecord]]:
        """
        Identify sensitive visual regions and apply solid black masking to the screenshot.
        Returns: (redacted_screenshot_b64, redactions_list)
        """
        if not screenshot_b64:
            return "", []

        redactions: List[VisualRedactionRecord] = []

        # 1. Correlate OCR text with visual regions to detect sensitive visual cards
        for ocr in ocr_regions:
            text_lower = ocr.text.lower()
            for cat, keywords in self.SENSITIVE_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    rec = VisualRedactionRecord(
                        redaction_id=f"vis_redact_{len(redactions) + 1}",
                        category=cat,
                        bounding_box=ocr.bounding_box,
                        confidence=max(0.85, ocr.confidence),
                        source="ocr_visual_correlation",
                        policy_decision="BLOCK",
                    )
                    redactions.append(rec)
                    break

        # 2. Check candidate visual regions marked as sensitive
        for vis in visual_regions:
            if vis.region_type == "sensitive_candidate" or (vis.label and "sensitive" in vis.label.lower()):
                rec = VisualRedactionRecord(
                    redaction_id=f"vis_redact_{len(redactions) + 1}",
                    category=VisualSensitiveCategory.PRIVATE_PROFILE,
                    bounding_box=vis.bounding_box,
                    confidence=vis.confidence,
                    source="local_cv_classifier",
                    policy_decision="LOCAL_ONLY",
                )
                redactions.append(rec)

        if not redactions:
            return screenshot_b64, []

        # 3. Apply solid black bounding-box masks locally
        try:
            img_bytes = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            draw = ImageDraw.Draw(image)

            for r in redactions:
                b = r.bounding_box
                x1 = b.get("x", 0)
                y1 = b.get("y", 0)
                x2 = x1 + b.get("width", 0)
                y2 = y1 + b.get("height", 0)
                # Draw solid black rectangle with 1px white border for audit visibility
                draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0), outline=(255, 255, 255))

            buf = io.BytesIO()
            image.save(buf, format="PNG")
            redacted_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            logger.info(f"[VisualPrivacy] Applied {len(redactions)} visual blackout mask(s) to screenshot.")
            return redacted_b64, redactions

        except Exception as e:
            logger.warning(f"[VisualPrivacy] Failed to apply visual redaction: {e}")
            # Fail closed: if visual redaction fails, return empty screenshot string to prevent raw leak!
            return "", redactions
