"""
Multimodal Perception Pipeline.
Orchestrates DOM extraction, screenshot processing, accessibility snapshot,
OCR text detection, and multimodal spatial fusion into a unified LocalWorldModel.
"""

import time
import logging
from typing import List, Tuple, Dict, Any, Optional

from webveil.core.models.schema import DOMNode, LocalWorldModel, TextRegion
from webveil.core.perception.screenshot import ScreenshotCapture
from webveil.core.perception.accessibility import AccessibilityExtractor
from webveil.core.perception.ocr import OCREngine
from webveil.core.perception.fusion import MultimodalFusionEngine, FusedPerceptionResult

logger = logging.getLogger("WebVeilPerception.Pipeline")


class MultimodalPerceptionPipeline:
    """
    Coordinates local multimodal perception across visual, accessibility, and DOM layers.
    Yields unified spatial world model with zero-PII leak invariants.
    """

    def __init__(self, ocr_enabled: bool = True):
        self.screenshot_capture = ScreenshotCapture()
        self.a11y_extractor = AccessibilityExtractor()
        self.ocr_engine = OCREngine(enabled=ocr_enabled)
        self.fusion_engine = MultimodalFusionEngine()

    def process_observation(
        self,
        page,
        dom_nodes: List[DOMNode],
        formatted_dom: str,
        screenshot_b64: str = "",
        url: str = "",
        title: str = "",
    ) -> Tuple[LocalWorldModel, Dict[str, float], FusedPerceptionResult]:
        """
        Execute full multimodal observation pipeline:
        1. Capture screenshot (if not provided)
        2. Extract accessibility tree & summary
        3. Run local OCR on screenshot
        4. Spatially fuse DOM + A11y + OCR
        5. Build unified LocalWorldModel
        
        Returns: (LocalWorldModel, timings_dict, FusedPerceptionResult)
        """
        timings: Dict[str, float] = {}

        # 1. Screenshot processing
        if not screenshot_b64 and page:
            t0 = time.time()
            _, screenshot_b64, _, _ = self.screenshot_capture.capture_viewport(page)
            timings["screenshot_capture_ms"] = (time.time() - t0) * 1000
        else:
            timings["screenshot_capture_ms"] = 0.0

        # 2. Accessibility tree extraction
        t0 = time.time()
        a11y_tree, a11y_summary = self.a11y_extractor.extract(page)
        timings["a11y_extraction_ms"] = (time.time() - t0) * 1000

        # 3. Visual OCR extraction
        t0 = time.time()
        ocr_regions: List[TextRegion] = self.ocr_engine.extract(screenshot_b64)
        timings["ocr_extraction_ms"] = (time.time() - t0) * 1000

        # 4. Multimodal Spatial Fusion
        t0 = time.time()
        fusion_result: FusedPerceptionResult = self.fusion_engine.fuse(
            dom_nodes=dom_nodes,
            a11y_tree=a11y_tree,
            ocr_regions=ocr_regions,
        )
        timings["multimodal_fusion_ms"] = (time.time() - t0) * 1000

        # 5. Extract raw page inner text if page available
        page_text = ""
        if page:
            try:
                page_text = page.inner_text("body")
            except Exception:
                pass

        # Build unified LocalWorldModel
        world_model = LocalWorldModel(
            url=url,
            title=title,
            dom_nodes=fusion_result.dom_nodes,
            formatted_dom=formatted_dom,
            a11y_tree=a11y_tree,
            a11y_summary=a11y_summary,
            ocr_regions=ocr_regions,
            screenshot_b64=screenshot_b64,
            page_text=page_text,
            timestamp=time.time(),
        )

        return world_model, timings, fusion_result
