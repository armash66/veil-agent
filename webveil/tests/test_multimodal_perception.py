"""
Unit tests for Phase 2: Local Multimodal Perception.
Verifies ScreenshotCapture, AccessibilityExtractor, OCREngine,
MultimodalFusionEngine, and MultimodalPerceptionPipeline.
"""

import unittest
from unittest.mock import MagicMock, patch

from webveil.core.models.schema import DOMNode, TextRegion
from webveil.core.perception.screenshot import ScreenshotCapture
from webveil.core.perception.accessibility import AccessibilityExtractor
from webveil.core.perception.ocr import OCREngine
from webveil.core.perception.fusion import MultimodalFusionEngine
from webveil.core.perception.pipeline import MultimodalPerceptionPipeline


class TestMultimodalPerception(unittest.TestCase):

    def test_screenshot_capture_safe_fallback(self):
        """Verify ScreenshotCapture gracefully handles None and errors."""
        raw, b64, w, h = ScreenshotCapture.capture_viewport(None)
        self.assertIsNone(raw)
        self.assertEqual(b64, "")
        self.assertEqual((w, h), (0, 0))

        raw_f, b64_f, w_f, h_f = ScreenshotCapture.capture_full_page(None)
        self.assertIsNone(raw_f)
        self.assertEqual(b64_f, "")
        self.assertEqual((w_f, h_f), (0, 0))

        # Check dimension calculation on empty string
        dims = ScreenshotCapture.get_dimensions("")
        self.assertEqual(dims, (0, 0))

    def test_accessibility_extractor_and_summary(self):
        """Verify ARIA tree extraction, summary generation, and interactive node flattening."""
        extractor = AccessibilityExtractor()

        mock_page = MagicMock()
        mock_tree = {
            "role": "main",
            "name": "Main Container",
            "children": [
                {
                    "role": "heading",
                    "name": "Welcome to WebVeil",
                    "children": []
                },
                {
                    "role": "button",
                    "name": "Submit Application",
                    "value": "submit_now",
                    "children": []
                },
                {
                    "role": "textbox",
                    "name": "Username",
                    "children": []
                }
            ]
        }
        mock_page.accessibility.snapshot.return_value = mock_tree

        tree, summary = extractor.extract(mock_page)
        self.assertIsNotNone(tree)
        self.assertIn('[main] "Main Container"', summary)
        self.assertIn('[button] "Submit Application"', summary)
        self.assertIn('value=submit_now', summary)
        self.assertIn('[textbox] "Username"', summary)

        # Verify flattening interactive elements
        interactive = extractor.flatten_interactive_nodes(tree)
        self.assertEqual(len(interactive), 2)
        roles = [i["role"] for i in interactive]
        self.assertIn("button", roles)
        self.assertIn("textbox", roles)

    def test_ocr_engine_summary_and_graceful_handling(self):
        """Verify OCREngine summary building and degradation."""
        ocr = OCREngine(enabled=True)
        # Empty screenshot should return empty list
        self.assertEqual(ocr.extract(""), [])

        sample_regions = [
            TextRegion(text="Sign In", bounding_box={"x": 100, "y": 50, "width": 80, "height": 30}, confidence=0.95),
            TextRegion(text="AWS Account ID", bounding_box={"x": 100, "y": 150, "width": 120, "height": 25}, confidence=0.92),
        ]
        summary = ocr.ocr_to_summary(sample_regions)
        self.assertIn("Visual Text Detected via OCR", summary)
        self.assertIn('"Sign In"', summary)
        self.assertIn('"AWS Account ID"', summary)

    def test_multimodal_fusion_spatial_alignment(self):
        """Verify 2D bounding box IoU, containment, and OCR-to-DOM enrichment."""
        engine = MultimodalFusionEngine()

        # Test IoU calculation
        b1 = {"x": 10, "y": 10, "width": 100, "height": 50}
        b2 = {"x": 10, "y": 10, "width": 100, "height": 50}
        self.assertEqual(engine.compute_iou(b1, b2), 1.0)

        # Disjoint boxes
        b3 = {"x": 200, "y": 200, "width": 50, "height": 50}
        self.assertEqual(engine.compute_iou(b1, b3), 0.0)

        # Containment
        inner = {"x": 20, "y": 20, "width": 30, "height": 20}
        self.assertTrue(engine.is_contained(inner, b1))
        self.assertFalse(engine.is_contained(b1, inner))

        # Fuse OCR text into DOM node missing text (e.g. icon or canvas button)
        canvas_button = DOMNode(
            node_id=42,
            tag_name="button",
            text_content="",  # Blank text in DOM
            bounding_box={"x": 50, "y": 100, "width": 120, "height": 40},
            is_interactive=True,
        )
        ocr_region = TextRegion(
            text="Proceed to Checkout",
            bounding_box={"x": 55, "y": 105, "width": 110, "height": 30},
            confidence=0.98,
        )

        a11y_tree = {
            "role": "button",
            "name": "Proceed to Checkout",
            "children": []
        }

        result = engine.fuse(
            dom_nodes=[canvas_button],
            a11y_tree=a11y_tree,
            ocr_regions=[ocr_region],
        )

        self.assertEqual(result.matched_ocr_count, 1)
        self.assertEqual(len(result.unmatched_ocr_regions), 0)
        self.assertEqual(canvas_button.text_content, "Proceed to Checkout")
        self.assertEqual(canvas_button.attributes.get("visual_ocr_text"), "Proceed to Checkout")
        self.assertEqual(canvas_button.attributes.get("aria_role"), "button")

    def test_multimodal_perception_pipeline_orchestration(self):
        """Verify full pipeline execution produces unified LocalWorldModel with timings."""
        pipeline = MultimodalPerceptionPipeline(ocr_enabled=False)

        mock_page = MagicMock()
        mock_page.accessibility.snapshot.return_value = {
            "role": "document",
            "name": "Portal",
            "children": [{"role": "button", "name": "Login", "children": []}]
        }
        mock_page.inner_text.return_value = "Welcome to Portal"

        dom_nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Login", is_interactive=True)
        ]

        model, timings, fusion = pipeline.process_observation(
            page=mock_page,
            dom_nodes=dom_nodes,
            formatted_dom="<button>Login</button>",
            screenshot_b64="fake_b64",
            url="https://portal.example.com",
            title="Portal Title",
        )

        self.assertEqual(model.url, "https://portal.example.com")
        self.assertEqual(model.title, "Portal Title")
        self.assertEqual(len(model.dom_nodes), 1)
        self.assertIn("Login", model.a11y_summary)
        self.assertIn("a11y_extraction_ms", timings)
        self.assertIn("multimodal_fusion_ms", timings)
        self.assertEqual(fusion.dom_nodes[0].node_id, 1)


if __name__ == "__main__":
    unittest.main()
