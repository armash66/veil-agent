"""
Local Vision Runtime Engine.
Manages client/browser-side vision model lifecycle, preprocessing,
viewport coordinate mapping, latency benchmarking, and visual region caching.
"""

import io
import base64
import time
import psutil
import logging
from typing import List, Dict, Any, Optional
from PIL import Image

from webveil.core.models.schema import VisualRegion
from webveil.core.perception.vision.base import LocalVisionModel, VisionModelMetadata
from webveil.core.perception.vision.ui_detector import LightweightUIVisionModel

logger = logging.getLogger("WebVeilPerception.VisionRuntime")


class LocalVisionRuntime:
    """
    Client-side visual inference runtime.
    Processes screenshots strictly locally and extracts structured visual regions
    with coordinate projection to browser viewport coordinates.
    """

    def __init__(self, model: Optional[LocalVisionModel] = None):
        self.model: LocalVisionModel = model or LightweightUIVisionModel()
        self.total_inferences: int = 0
        self.cumulative_latency_ms: float = 0.0
        self.last_metadata: Optional[VisionModelMetadata] = None

    def process_screenshot(
        self,
        screenshot_b64: str,
        viewport: Optional[Dict[str, float]] = None,
    ) -> List[VisualRegion]:
        """
        Run client-side vision perception on screenshot.
        """
        if not screenshot_b64:
            return []

        t0 = time.perf_counter()
        try:
            # Decode image from base64 locally
            img_bytes = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            logger.warning(f"[VisionRuntime] Failed to decode screenshot image: {e}")
            return []

        # Run local vision model inference
        regions = self.model.detect_regions(image, viewport=viewport)

        # Coordinate sanity filtering
        valid_regions = []
        for r in regions:
            b = r.bounding_box
            if b.get("width", 0) > 4 and b.get("height", 0) > 4:
                valid_regions.append(r)

        # Postprocess: Non-Maximum Suppression (NMS) to eliminate duplicate overlapping regions
        deduped = self._nms_deduplicate(valid_regions, iou_threshold=0.65)

        t_elapsed = (time.perf_counter() - t0) * 1000.0
        self.total_inferences += 1
        self.cumulative_latency_ms += t_elapsed
        self.last_metadata = self.model.get_metadata()
        self.last_metadata.inference_latency_ms = t_elapsed

        logger.info(
            f"[VisionRuntime] Processed screenshot -> {len(deduped)} visual regions in {t_elapsed:.1f}ms "
            f"(Backend: {self.last_metadata.backend})"
        )
        return deduped

    def get_runtime_stats(self) -> Dict[str, Any]:
        """Return runtime performance and resource measurements."""
        avg_lat = (self.cumulative_latency_ms / max(1, self.total_inferences))
        meta = self.model.get_metadata()
        return {
            "total_inferences": self.total_inferences,
            "average_latency_ms": round(avg_lat, 2),
            "model_metadata": meta.to_dict(),
        }

    @staticmethod
    def _nms_deduplicate(regions: List[VisualRegion], iou_threshold: float = 0.65) -> List[VisualRegion]:
        """Eliminate redundant visual bounding boxes with high overlap."""
        if len(regions) <= 1:
            return regions

        # Sort descending by confidence
        sorted_regions = sorted(regions, key=lambda r: r.confidence, reverse=True)
        kept: List[VisualRegion] = []

        for cand in sorted_regions:
            b1 = cand.bounding_box
            overlap = False
            for prev in kept:
                b2 = prev.bounding_box
                # Calculate IoU
                x1 = max(b1.get("x", 0), b2.get("x", 0))
                y1 = max(b1.get("y", 0), b2.get("y", 0))
                x2 = min(b1.get("x", 0) + b1.get("width", 0), b2.get("x", 0) + b2.get("width", 0))
                y2 = min(b1.get("y", 0) + b1.get("height", 0), b2.get("y", 0) + b2.get("height", 0))

                inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                area1 = b1.get("width", 0) * b1.get("height", 0)
                area2 = b2.get("width", 0) * b2.get("height", 0)
                union = area1 + area2 - inter
                iou = inter / max(1.0, union)

                if iou > iou_threshold and cand.region_type == prev.region_type:
                    overlap = True
                    break

            if not overlap:
                kept.append(cand)

        return kept
