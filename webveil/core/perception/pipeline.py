"""
Multimodal Perception Pipeline.
Orchestrates DOM extraction, screenshot processing, accessibility snapshot,
OCR text detection, and multimodal spatial fusion into a unified LocalWorldModel.
"""

import time
import logging
from typing import List, Tuple, Dict, Any, Optional

from webveil.core.models.schema import DOMNode, LocalWorldModel, TextRegion, VisualRegion
from webveil.core.perception.screenshot import ScreenshotCapture
from webveil.core.perception.accessibility import AccessibilityExtractor
from webveil.core.perception.ocr import OCREngine
from webveil.core.perception.fusion import MultimodalFusionEngine, FusedPerceptionResult
from webveil.core.perception.adaptive_router import AdaptivePerceptionRouter, PerceptionModality
from webveil.core.perception.vision.runtime import LocalVisionRuntime
from webveil.core.perception.vision.base import LocalVisionModel

logger = logging.getLogger("WebVeilPerception.Pipeline")


class MultimodalPerceptionPipeline:
    """
    Coordinates local multimodal perception across visual, accessibility, and DOM layers.
    Yields unified spatial world model with zero-PII leak invariants and resource-aware routing.
    """

    def __init__(self, ocr_enabled: bool = True, vision_model: Optional[LocalVisionModel] = None):
        self.screenshot_capture = ScreenshotCapture()
        self.a11y_extractor = AccessibilityExtractor()
        self.ocr_engine = OCREngine(enabled=ocr_enabled)
        self.vision_runtime = LocalVisionRuntime(model=vision_model)
        self.fusion_engine = MultimodalFusionEngine()
        self.adaptive_router = AdaptivePerceptionRouter()

    def process_observation(
        self,
        page,
        dom_nodes: List[DOMNode],
        formatted_dom: str,
        screenshot_b64: str = "",
        url: str = "",
        title: str = "",
        user_task: str = "",
        adaptive: bool = False,
    ) -> Tuple[LocalWorldModel, Dict[str, float], FusedPerceptionResult]:
        """
        Execute multimodal observation pipeline with adaptive resource routing.
        
        Returns: (LocalWorldModel, timings_dict, FusedPerceptionResult)
        """
        timings: Dict[str, float] = {}

        # 0. Adaptive Modality Selection
        has_canvas = any(n.tag_name == "canvas" for n in dom_nodes)
        modality, reason = self.adaptive_router.determine_modality(
            dom_nodes=dom_nodes, page_has_canvas=has_canvas, user_task=user_task
        )
        timings["modality"] = modality.value

        # 1. Screenshot processing
        skip_visual = (adaptive and modality == PerceptionModality.DOM_A11Y_FAST and not screenshot_b64)
        if not skip_visual and not screenshot_b64 and page:
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
        ocr_regions: List[TextRegion] = []
        if not skip_visual and screenshot_b64:
            t0 = time.time()
            ocr_regions = self.ocr_engine.extract(screenshot_b64)
            timings["ocr_extraction_ms"] = (time.time() - t0) * 1000
        else:
            timings["ocr_extraction_ms"] = 0.0

        # 4. Local CV / Visual UI Structure Extraction
        visual_regions: List[VisualRegion] = []
        if not skip_visual and screenshot_b64:
            t0 = time.time()
            visual_regions = self.vision_runtime.process_screenshot(screenshot_b64)
            timings["local_vision_ms"] = (time.time() - t0) * 1000
        else:
            timings["local_vision_ms"] = 0.0

        # 5. Multimodal Spatial Fusion across DOM, A11y, OCR, and Vision
        t0 = time.time()
        fusion_result: FusedPerceptionResult = self.fusion_engine.fuse(
            dom_nodes=dom_nodes,
            a11y_tree=a11y_tree,
            ocr_regions=ocr_regions,
            visual_regions=visual_regions,
        )
        timings["multimodal_fusion_ms"] = (time.time() - t0) * 1000

        # 6. Extract raw page inner text if page available
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
            visual_regions=visual_regions,
            dialogs_detected=fusion_result.dialogs_detected,
            screenshot_b64=screenshot_b64,
            page_text=page_text,
            timestamp=time.time(),
        )

        return world_model, timings, fusion_result
