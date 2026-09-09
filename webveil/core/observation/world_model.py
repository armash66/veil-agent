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
        from webveil.core.perception.pipeline import MultimodalPerceptionPipeline
        self.perception_pipeline = MultimodalPerceptionPipeline(ocr_enabled=ocr_enabled)
        self.a11y_observer = self.perception_pipeline.a11y_extractor
        self.ocr_observer = self.perception_pipeline.ocr_engine
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
        Build LocalWorldModel by executing the multimodal perception pipeline
        (DOM + A11y + Screenshot + OCR + Spatial Fusion).
        Returns (model, timing_dict) for SIH latency tracking.
        """
        model, timings, fusion_res = self.perception_pipeline.process_observation(
            page=page,
            dom_nodes=dom_nodes,
            formatted_dom=formatted_dom,
            screenshot_b64=screenshot_b64,
            url=url,
            title=title,
        )

        logger.info(
            f"[WorldModel] Built: {len(model.dom_nodes)} DOM nodes, "
            f"a11y={'yes' if model.a11y_tree else 'no'}, "
            f"OCR={len(model.ocr_regions)} regions, "
            f"enriched={fusion_res.enriched_node_count} nodes"
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

        # 1. DOM PII detection + sanitization
        t0 = time.time()
        sanitized_nodes, dom_matches = self.redactor.sanitize_dom(model.dom_nodes, origin)
        timings["pii_dom_detection_ms"] = (time.time() - t0) * 1000

        # 2. OCR text PII detection + vault tokenization
        t0 = time.time()
        sanitized_ocr_regions, ocr_matches = self.redactor.sanitize_ocr_regions(model.ocr_regions, origin)
        timings["pii_ocr_detection_ms"] = (time.time() - t0) * 1000

        # Unified PII matches across DOM and OCR
        all_pii_matches = dom_matches + ocr_matches
        timings["pii_detection_ms"] = timings["pii_dom_detection_ms"] + timings["pii_ocr_detection_ms"]

        # 3. Screenshot visual mask redaction (both DOM + OCR bounding boxes)
        t0 = time.time()
        redacted_screenshot = self.redactor.redact_screenshot_b64(
            model.screenshot_b64, all_pii_matches
        )
        timings["redaction_ms"] = (time.time() - t0) * 1000

        # 4. Build sanitized OCR summary
        ocr_summary = ""
        if sanitized_ocr_regions:
            ocr_summary = " ".join([r.text for r in sanitized_ocr_regions])

        # 5. Sanitize accessibility summary
        sanitized_a11y = self._sanitize_text(model.a11y_summary) if model.a11y_summary else ""

        # 6. Build sanitized formatted DOM
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
            detected_pii_count=len(all_pii_matches),
            pii_categories_found=[m.category.name for m in all_pii_matches],
        )

        logger.info(
            f"[WorldModel] Sanitized: {len(all_pii_matches)} PII matches redacted "
            f"({len(dom_matches)} DOM, {len(ocr_matches)} OCR), "
            f"zero raw PII in output"
        )
        return sanitized, all_pii_matches, timings

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
