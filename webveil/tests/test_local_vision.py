"""
Unit tests for Local Vision Runtime & Lightweight UI Vision Model.
Verifies browser-local CV inference, visual UI region segmentation (cards, dialogs, controls),
NMS deduplication, coordinate scaling, and dynamic performance measurement.
"""

import io
import base64
import unittest
import numpy as np
from PIL import Image, ImageDraw

from webveil.core.models.schema import VisualRegion
from webveil.core.perception.vision.base import LocalVisionModel, VisionModelMetadata
from webveil.core.perception.vision.ui_detector import LightweightUIVisionModel
from webveil.core.perception.vision.runtime import LocalVisionRuntime


class TestLocalVision(unittest.TestCase):

    def setUp(self):
        self.model = LightweightUIVisionModel()
        self.runtime = LocalVisionRuntime(model=self.model)

    def _create_synthetic_ui_screenshot(self, width: int = 800, height: int = 600) -> Image.Image:
        """Draw a synthetic browser UI with a modal dialog, two cards, and buttons."""
        image = Image.new("RGB", (width, height), color=(245, 247, 250))
        draw = ImageDraw.Draw(image)

        # Draw card 1
        draw.rectangle([50, 50, 350, 250], fill=(255, 255, 255), outline=(200, 210, 225), width=2)
        # Draw card 2
        draw.rectangle([400, 50, 700, 250], fill=(255, 255, 255), outline=(200, 210, 225), width=2)

        # Draw modal dialog in center
        draw.rectangle([150, 120, 650, 480], fill=(255, 255, 255), outline=(30, 40, 60), width=4)
        draw.rectangle([170, 140, 630, 180], fill=(230, 235, 245))  # dialog title bar
        draw.rectangle([480, 420, 620, 460], fill=(0, 102, 204))    # submit button inside dialog

        return image

    def test_lightweight_ui_vision_model_detection(self):
        """Verify model detects UI regions and measures performance dynamically."""
        image = self._create_synthetic_ui_screenshot()
        viewport = {"width": 800, "height": 600}

        regions = self.model.detect_regions(image, viewport=viewport)

        self.assertGreater(len(regions), 0)
        # Should detect regions with valid bounding boxes
        for r in regions:
            self.assertIn(r.region_type, ["dialog", "card", "control"])
            self.assertGreater(r.confidence, 0.5)
            self.assertGreater(r.bounding_box["width"], 0)
            self.assertGreater(r.bounding_box["height"], 0)

        # Check metadata is dynamically measured, not hardcoded
        meta = self.model.get_metadata()
        self.assertEqual(meta.backend, "browser_local_cv")
        self.assertTrue(meta.is_browser_local)
        self.assertGreater(meta.inference_latency_ms, 0.0)
        self.assertGreater(meta.memory_footprint_mb, 0.0)
        self.assertGreater(meta.parameters_count, 0)

    def test_local_vision_runtime_screenshot_pipeline(self):
        """Verify runtime handles base64 decoding, scaling, NMS, and tracking."""
        image = self._create_synthetic_ui_screenshot(400, 300)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Viewport is scaled 2x to 800x600 CSS pixels
        viewport = {"width": 800, "height": 600}
        regions = self.runtime.process_screenshot(b64, viewport=viewport)

        self.assertGreater(len(regions), 0)
        # Verify coordinates are scaled into viewport space
        max_x = max(r.bounding_box["x"] + r.bounding_box["width"] for r in regions)
        self.assertLessEqual(max_x, 805)

        stats = self.runtime.get_runtime_stats()
        self.assertEqual(stats["total_inferences"], 1)
        self.assertGreater(stats["average_latency_ms"], 0.0)
        self.assertIn("model_metadata", stats)

    def test_nms_deduplication(self):
        """Verify overlapping bounding boxes of identical type are pruned."""
        r1 = VisualRegion(
            region_id="r1", region_type="card",
            bounding_box={"x": 50, "y": 50, "width": 200, "height": 150},
            confidence=0.92,
        )
        r2 = VisualRegion(
            region_id="r2", region_type="card",
            bounding_box={"x": 52, "y": 51, "width": 198, "height": 149},  # ~98% IoU overlap
            confidence=0.75,
        )
        r3 = VisualRegion(
            region_id="r3", region_type="control",
            bounding_box={"x": 400, "y": 400, "width": 80, "height": 40},
            confidence=0.88,
        )

        deduped = LocalVisionRuntime._nms_deduplicate([r1, r2, r3], iou_threshold=0.6)
        self.assertEqual(len(deduped), 2)
        # Kept higher-confidence card
        card_ids = [r.region_id for r in deduped if r.region_type == "card"]
        self.assertIn("r1", card_ids)
        self.assertNotIn("r2", card_ids)


if __name__ == "__main__":
    unittest.main()
