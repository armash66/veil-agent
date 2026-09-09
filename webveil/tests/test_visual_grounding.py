"""
Unit tests for Phase 7: Visual Grounding.
Verifies CoordinateMapper, VisualElementMatcher, GroundingVerifier,
and enhanced ElementGrounder with physical coordinate generation.
"""

import unittest
from webveil.core.models.schema import DOMNode, BrowserAction, ActionType, TextRegion
from webveil.core.grounding.coordinate_mapper import CoordinateMapper
from webveil.core.grounding.visual_matcher import VisualElementMatcher
from webveil.core.grounding.grounding_verifier import GroundingVerifier
from webveil.core.grounding.element_grounder import ElementGrounder


class TestVisualGrounding(unittest.TestCase):

    def test_coordinate_mapper_calculations(self):
        """Verify element center calculation, viewport mapping, and bounds checking."""
        box = {"x": 100.0, "y": 200.0, "width": 80.0, "height": 40.0}
        center = CoordinateMapper.get_element_center(box)
        self.assertEqual(center, (140.0, 220.0))

        # Viewport mapping with scroll offset (scroll_x=40, scroll_y=50)
        vp_point = CoordinateMapper.map_to_viewport(center, scroll_offset=(40.0, 50.0))
        self.assertEqual(vp_point, (100.0, 170.0))

        # Viewport boundary check
        self.assertTrue(CoordinateMapper.is_in_viewport(vp_point, (1280, 720)))
        self.assertFalse(CoordinateMapper.is_in_viewport((1500.0, 100.0), (1280, 720)))
        self.assertFalse(CoordinateMapper.is_in_viewport((-10.0, 50.0), (1280, 720)))

        # Safe click point dict
        click_point = CoordinateMapper.compute_safe_click_point(box, scroll_offset=(0.0, 0.0), viewport_size=(1280, 720))
        self.assertEqual(click_point["x"], 140.0)
        self.assertEqual(click_point["y"], 220.0)
        self.assertTrue(click_point["is_in_viewport"])

    def test_visual_element_matcher_dom_and_ocr(self):
        """Verify visual target matching across DOM nodes and OCR regions."""
        matcher = VisualElementMatcher()

        dom_nodes = [
            DOMNode(node_id=10, tag_name="input", element_type="text", text_content="Search", bounding_box={"x": 50, "y": 50, "width": 100, "height": 30}, is_interactive=True),
            DOMNode(node_id=11, tag_name="button", text_content="Checkout", bounding_box={"x": 50, "y": 120, "width": 80, "height": 30}, is_interactive=True),
        ]
        ocr_regions = [
            TextRegion(text="Canvas Login Button", bounding_box={"x": 50, "y": 200, "width": 90, "height": 35}, confidence=0.95),
        ]

        # 1. Match by explicit node_id
        action_node = BrowserAction(action=ActionType.CLICK, node_id=11)
        res1 = matcher.match_visual_target(action_node, dom_nodes, ocr_regions)
        self.assertEqual(res1.matched_node_id, 11)
        self.assertEqual(res1.source, "dom")

        # 2. Match canvas button via OCR text in thought
        action_canvas = BrowserAction(action=ActionType.CLICK, node_id=None, thought='Click the "Canvas Login Button"')
        res2 = matcher.match_visual_target(action_canvas, dom_nodes, ocr_regions)
        self.assertEqual(res2.source, "ocr")
        self.assertEqual(res2.bounding_box, {"x": 50, "y": 200, "width": 90, "height": 35})

    def test_grounding_verifier_checks(self):
        """Verify target interactability checks and modal obstruction detection."""
        verifier = GroundingVerifier()

        visible_node = DOMNode(node_id=1, tag_name="button", is_visible=True)
        hidden_node = DOMNode(node_id=2, tag_name="button", is_visible=False)

        valid_coords = {"x": 200.0, "y": 150.0}
        out_of_bounds_coords = {"x": 2000.0, "y": 150.0}

        # Visible + valid coords
        ok1, _ = verifier.verify_target_interactable(visible_node, valid_coords)
        self.assertTrue(ok1)

        # Hidden node -> fail
        ok2, msg2 = verifier.verify_target_interactable(hidden_node, valid_coords)
        self.assertFalse(ok2)
        self.assertIn("non-visible", msg2)

        # Out of bounds coords -> fail
        ok3, msg3 = verifier.verify_target_interactable(visible_node, out_of_bounds_coords)
        self.assertFalse(ok3)
        self.assertIn("outside active viewport", msg3)

        # Modal obstruction check
        modal_node = DOMNode(
            node_id=99,
            tag_name="dialog",
            is_visible=True,
            bounding_box={"x": 300, "y": 200, "width": 400, "height": 300},
        )
        target_outside_modal = {"x": 50, "y": 50, "width": 100, "height": 30}
        target_inside_modal = {"x": 350, "y": 250, "width": 100, "height": 30}

        self.assertTrue(verifier.check_modal_obstruction(target_outside_modal, [modal_node]))
        self.assertFalse(verifier.check_modal_obstruction(target_inside_modal, [modal_node]))

    def test_element_grounder_coordinates_integration(self):
        """Verify ElementGrounder computes physical click coordinates in GroundingResult."""
        grounder = ElementGrounder()

        node = DOMNode(
            node_id=7,
            tag_name="button",
            text_content="Submit Application",
            is_visible=True,
            is_interactive=True,
            bounding_box={"x": 100.0, "y": 150.0, "width": 120.0, "height": 40.0},
        )

        action = BrowserAction(action=ActionType.CLICK, node_id=7, thought="Click submit")
        result = grounder.ground_action(action, [node])

        self.assertEqual(result.threshold_action, "EXECUTE")
        self.assertIsNotNone(result.target_coordinates)
        self.assertEqual(result.target_coordinates["x"], 160.0)
        self.assertEqual(result.target_coordinates["y"], 170.0)
        self.assertTrue(result.is_in_viewport)


if __name__ == "__main__":
    unittest.main()
