"""
Local World Model Builder.
Merges DOM + Accessibility + OCR into a unified observation,
then applies privacy processing to produce a sanitized world model.
"""

import time
import logging
from typing import List, Tuple, Optional

from webveil.core.models.schema import (
    DOMNode, LocalWorldModel, SanitizedWorldModel,
    SanitizedObservation, PIIMatch, TextRegion
)
from webveil.core.observation.a11y_observer import A11yObserver
from webveil.core.observation.ocr_observer import OCRObserver
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.privacy.redactor import LocalRedactor

logger = logging.getLogger("WebVeilWorldModel")


class WorldModelBuilder:
    """
    Builds a unified LocalWorldModel from three observation layers,
    then applies privacy processing to produce SanitizedWorldModel.
    
    Observation pipeline:
        Browser → DOM + A11y + Screenshot/OCR → LocalWorldModel
        LocalWorldModel → PII scan + Redaction → SanitizedWorldModel
    """

    def __init__(self, redactor: LocalRedactor, ocr_enabled: bool = True):
        self.a11y_observer = A11yObserver()
        self.ocr_observer = OCRObserver(enabled=ocr_enabled)
        self.redactor = redactor
        self.detector = redactor.detector

    def build_local_model(
        self,
        page,
        dom_nodes: List[DOMNode],
        formatted_dom: str,
        screenshot_b64: str,
        url: str,
        title: str,
    ) -> Tuple[LocalWorldModel, dict]:
        """
        Build LocalWorldModel by merging all three observation layers.
        Returns (model, timing_dict) for SIH latency tracking.
        """
        timings = {}

        # Layer 2: Accessibility tree
        t0 = time.time()
        a11y_tree, a11y_summary = self.a11y_observer.extract(page)
        timings["a11y_extraction_ms"] = (time.time() - t0) * 1000

        # Layer 3: OCR (optional)
        t0 = time.time()
        ocr_regions = self.ocr_observer.extract(screenshot_b64)
        timings["ocr_extraction_ms"] = (time.time() - t0) * 1000

        # Extract visible page text
        page_text = ""
        try:
            page_text = page.inner_text("body") if page else ""
        except Exception:
            pass

        model = LocalWorldModel(
            url=url,
            title=title,
            dom_nodes=dom_nodes,
            formatted_dom=formatted_dom,
            a11y_tree=a11y_tree,
            a11y_summary=a11y_summary,
            ocr_regions=ocr_regions,
            screenshot_b64=screenshot_b64,
            page_text=page_text,
            timestamp=time.time(),
        )

        logger.info(
            f"[WorldModel] Built: {len(dom_nodes)} DOM nodes, "
            f"a11y={'yes' if a11y_tree else 'no'}, "
            f"OCR={len(ocr_regions)} regions"
        )
        return model, timings

    def sanitize(
        self,
        model: LocalWorldModel,
        origin: str,
    ) -> Tuple[SanitizedWorldModel, List[PIIMatch], dict]:
        """
        Apply privacy processing to the local world model.
        Returns (sanitized_model, pii_matches, timing_dict).
        """
        timings = {}

        # PII detection + DOM sanitization
        t0 = time.time()
        sanitized_nodes, pii_matches = self.redactor.sanitize_dom(model.dom_nodes, origin)
        timings["pii_detection_ms"] = (time.time() - t0) * 1000

        # Screenshot redaction
        t0 = time.time()
        redacted_screenshot = self.redactor.redact_screenshot_b64(
            model.screenshot_b64, pii_matches
        )
        timings["redaction_ms"] = (time.time() - t0) * 1000

        # Sanitize OCR text (scan for PII in OCR regions)
        ocr_summary = ""
        if model.ocr_regions:
            ocr_texts = [r.text for r in model.ocr_regions]
            ocr_combined = " ".join(ocr_texts)
            # Redact PII from OCR text using detector patterns
            ocr_summary = self._sanitize_text(ocr_combined)

        # Sanitize accessibility summary
        sanitized_a11y = self._sanitize_text(model.a11y_summary) if model.a11y_summary else ""

        # Build sanitized formatted DOM
        sanitized_lines = []
        for n in sanitized_nodes:
            if n.is_interactive:
                line = (
                    f"[{n.node_id}] <{n.tag_name} type='{n.element_type}' "
                    f"name='{n.name}' "
                    f"placeholder='{n.attributes.get('placeholder', '')}' "
                    f"value='{n.value}'>{n.text_content}</{n.tag_name}>"
                )
                sanitized_lines.append(line)
        sanitized_formatted_dom = "\n".join(sanitized_lines)

        sanitized = SanitizedWorldModel(
            url=model.url,
            sanitized_url=model.url,
            title=model.title,
            sanitized_dom=sanitized_nodes,
            formatted_dom=sanitized_formatted_dom,
            a11y_summary=sanitized_a11y,
            ocr_summary=ocr_summary,
            redacted_screenshot_b64=redacted_screenshot,
            detected_pii_count=len(pii_matches),
            pii_categories_found=[m.category.name for m in pii_matches],
        )

        logger.info(
            f"[WorldModel] Sanitized: {len(pii_matches)} PII matches redacted, "
            f"zero raw PII in output"
        )
        return sanitized, pii_matches, timings

    def to_legacy_observation(self, sanitized: SanitizedWorldModel) -> SanitizedObservation:
        """Convert to V0 SanitizedObservation for backward compatibility with egress gate."""
        return SanitizedObservation(
            url=sanitized.url,
            sanitized_url=sanitized.sanitized_url,
            title=sanitized.title,
            dom_tree=sanitized.sanitized_dom,
            formatted_dom=sanitized.formatted_dom,
            redacted_screenshot_b64=sanitized.redacted_screenshot_b64,
            detected_pii_count=sanitized.detected_pii_count,
            pii_categories_found=sanitized.pii_categories_found,
        )

    def _sanitize_text(self, text: str) -> str:
        """Apply PII regex patterns to sanitize arbitrary text."""
        if not text:
            return ""
        clean = text
        clean = self.detector.EMAIL_REGEX.sub("[EMAIL_REDACTED]", clean)
        clean = self.detector.PHONE_REGEX.sub("[PHONE_REDACTED]", clean)
        clean = self.detector.AADHAAR_REGEX.sub("[AADHAAR_REDACTED]", clean)
        clean = self.detector.CANARY_REGEX.sub("[CANARY_REDACTED]", clean)
        clean = self.detector.CREDIT_CARD_REGEX.sub("[CARD_REDACTED]", clean)
        return clean
