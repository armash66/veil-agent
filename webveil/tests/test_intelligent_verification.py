"""
Unit tests for Intelligent Multi-Criterion Verification Engine.
Tests negative error scanning, DOM mutation tracking, navigation state changes,
and confidence-driven replan triggers.
"""

import unittest
from webveil.core.models.schema import DOMNode, BrowserAction, ActionType
from webveil.core.verification.intelligent_verifier import (
    IntelligentVerifier,
    VerificationStatus,
)
from webveil.core.verification.local_verifier import LocalVerifier


class TestIntelligentVerification(unittest.TestCase):

    def setUp(self):
        self.verifier = IntelligentVerifier()
        self.local_verifier = LocalVerifier()

    def test_negative_error_detection_triggers_replan(self):
        """Verify presence of error banner fails verification and requests replan."""
        prev_nodes = [DOMNode(node_id=1, tag_name="button", text_content="Log In", is_visible=True)]
        curr_nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Log In", is_visible=True),
            DOMNode(node_id=2, tag_name="div", text_content="Error: Invalid credentials provided.", is_visible=True),
        ]

        action = BrowserAction(action=ActionType.CLICK, node_id=1)
        result = self.verifier.verify_action_execution(action, prev_nodes, curr_nodes)

        self.assertEqual(result.status, VerificationStatus.NEGATIVE_ERROR_DETECTED)
        self.assertTrue(result.should_replan)
        self.assertLess(result.confidence, 0.5)
        self.assertIn("Invalid credentials", result.detected_errors[0])

        # LocalVerifier backward compatibility
        self.assertFalse(self.local_verifier.verify_action_execution(action, prev_nodes, curr_nodes))

    def test_navigation_verification(self):
        """Verify navigation updates URL and confirms transition."""
        action = BrowserAction(action=ActionType.NAVIGATE, url="https://github.com/login")

        # Success case
        res_ok = self.verifier.verify_action_execution(
            action, [], [], previous_url="https://github.com", current_url="https://github.com/login"
        )
        self.assertEqual(res_ok.status, VerificationStatus.SUCCESS)
        self.assertGreaterEqual(res_ok.confidence, 0.9)
        self.assertFalse(res_ok.should_replan)

        # Failure case (URL unchanged)
        res_fail = self.verifier.verify_action_execution(
            action, [], [], previous_url="https://github.com", current_url="https://github.com"
        )
        self.assertEqual(res_fail.status, VerificationStatus.FAILURE)
        self.assertTrue(res_fail.should_replan)

    def test_dom_mutation_and_click_verification(self):
        """Verify click that produces DOM mutations passes with high confidence."""
        prev_nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Open Modal", is_visible=True),
        ]
        curr_nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Open Modal", is_visible=True),
            DOMNode(node_id=2, tag_name="div", text_content="Confirmation Dialog", is_visible=True),
            DOMNode(node_id=3, tag_name="button", text_content="Confirm", is_visible=True),
        ]

        action = BrowserAction(action=ActionType.CLICK, node_id=1)
        result = self.verifier.verify_action_execution(action, prev_nodes, curr_nodes)

        self.assertEqual(result.status, VerificationStatus.SUCCESS)
        self.assertEqual(result.dom_mutations_count, 2)
        self.assertGreaterEqual(result.confidence, 0.85)
        self.assertFalse(result.should_replan)

    def test_stagnant_click_triggers_partial_replan(self):
        """Verify click producing zero changes triggers replan flag."""
        same_nodes = [DOMNode(node_id=1, tag_name="button", text_content="Click Me", is_visible=True)]
        action = BrowserAction(action=ActionType.CLICK, node_id=1)

        result = self.verifier.verify_action_execution(action, same_nodes, same_nodes)
        self.assertEqual(result.status, VerificationStatus.PARTIAL_SUCCESS)
        self.assertTrue(result.should_replan)
        self.assertLess(result.confidence, 0.70)

    def test_done_action_success_indicator(self):
        """Verify DONE action recognizes success confirmation."""
        nodes = [
            DOMNode(node_id=1, tag_name="h1", text_content="Order Placed! Thank you for your purchase.", is_visible=True)
        ]
        action = BrowserAction(action=ActionType.DONE)
        result = self.verifier.verify_action_execution(action, nodes, nodes, user_task="Place order")

        self.assertEqual(result.status, VerificationStatus.SUCCESS)
        self.assertGreaterEqual(result.confidence, 0.88)
        self.assertFalse(result.should_replan)


if __name__ == "__main__":
    unittest.main()
