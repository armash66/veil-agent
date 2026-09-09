"""
Unit tests for Resource-Aware Adaptive Perception Routing.
Verifies dynamic modality selection and latency optimization across web archetypes.
"""

import unittest
from unittest.mock import MagicMock

from webveil.core.models.schema import DOMNode
from webveil.core.perception.adaptive_router import AdaptivePerceptionRouter, PerceptionModality
from webveil.core.perception.pipeline import MultimodalPerceptionPipeline


class TestAdaptivePerception(unittest.TestCase):

    def setUp(self):
        self.router = AdaptivePerceptionRouter()

    def test_standard_dom_selects_fast_modality(self):
        """Verify standard rich DOM uses fast DOM+A11y path."""
        nodes = [
            DOMNode(node_id=1, tag_name="input", element_type="text", text_content="", attributes={"placeholder": "Search query"}, is_interactive=True),
            DOMNode(node_id=2, tag_name="button", text_content="Submit", is_interactive=True),
            DOMNode(node_id=3, tag_name="p", text_content="Welcome to our platform article."),
        ]
        modality, reason = self.router.determine_modality(nodes, user_task="Search for products")
        self.assertEqual(modality, PerceptionModality.DOM_A11Y_FAST)
        self.assertIn("fast path", reason)

    def test_canvas_element_triggers_visual_perception(self):
        """Verify page containing canvas element escalates to visual modality."""
        nodes = [
            DOMNode(node_id=1, tag_name="canvas", text_content="", is_interactive=True),
            DOMNode(node_id=2, tag_name="div", text_content="Interactive Canvas Widget"),
        ]
        modality, reason = self.router.determine_modality(nodes, page_has_canvas=True, user_task="Click matching target")
        self.assertEqual(modality, PerceptionModality.CANVAS_VISION)
        self.assertIn("canvas", reason)

    def test_unlabeled_elements_trigger_multimodal(self):
        """Verify icon-only or unlabeled interactive elements trigger OCR."""
        nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="", is_interactive=True),
            DOMNode(node_id=2, tag_name="button", text_content="", is_interactive=True),
            DOMNode(node_id=3, tag_name="button", text_content="Help", is_interactive=True),
        ]
        modality, reason = self.router.determine_modality(nodes, user_task="Click icon")
        self.assertEqual(modality, PerceptionModality.MULTIMODAL_FULL)

    def test_visual_keyword_task_triggers_multimodal(self):
        """Verify user task mentioning visual chart/diagram escalates to multimodal."""
        nodes = [
            DOMNode(node_id=1, tag_name="div", text_content="Monthly report"),
        ]
        modality, reason = self.router.determine_modality(nodes, user_task="Look at the revenue chart and extract total")
        self.assertEqual(modality, PerceptionModality.MULTIMODAL_FULL)

    def test_pipeline_skips_ocr_in_adaptive_mode(self):
        """Verify MultimodalPerceptionPipeline skips OCR when adaptive routing selects fast mode."""
        pipeline = MultimodalPerceptionPipeline(ocr_enabled=True)
        mock_page = MagicMock()
        mock_page.accessibility.snapshot.return_value = {"role": "WebArea", "name": "Test Page"}
        mock_page.inner_text.return_value = "Page content"

        nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Next Step", is_interactive=True),
        ]

        model, timings, _ = pipeline.process_observation(
            page=mock_page,
            dom_nodes=nodes,
            formatted_dom="<button>Next Step</button>",
            url="https://example.com",
            user_task="Click Next Step",
            adaptive=True,
        )

        self.assertEqual(timings["modality"], PerceptionModality.DOM_A11Y_FAST.value)
        self.assertEqual(timings["ocr_extraction_ms"], 0.0)
        self.assertEqual(len(model.ocr_regions), 0)


if __name__ == "__main__":
    unittest.main()
