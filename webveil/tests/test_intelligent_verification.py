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

    def test_agent_verification_failure_triggers_replan_with_error_context(self):
        """Verify that when verification fails in WebVeilAgent, it transitions to REPLAN with error context."""
        from unittest.mock import MagicMock, patch
        from webveil.agent_loop import WebVeilAgent
        from webveil.core.models.state import AgentStage
        from webveil.core.models.schema import ActionPlan

        with patch("webveil.agent_loop.PlaywrightAdapter") as mock_playwright_cls:
            mock_browser = MagicMock()
            mock_playwright_cls.return_value = mock_browser

            # Initial page
            initial_node = DOMNode(node_id=1, tag_name="button", text_content="Submit", is_visible=True, is_interactive=True)
            # Post page displays an error banner
            error_node = DOMNode(node_id=2, tag_name="div", text_content="Error: Invalid credentials provided.", is_visible=True)

            mock_browser.extract_dom.side_effect = [
                ([initial_node], "<button>Submit</button>"),  # step 1 observe
                ([initial_node, error_node], "<button>Submit</button><div>Error: Invalid credentials</div>"),  # step 1 post-verify
                ([initial_node, error_node], "<button>Submit</button><div>Error: Invalid credentials</div>"),  # step 2 observe
                ([initial_node, error_node], "<button>Submit</button><div>Error: Invalid credentials</div>"),  # step 2 post-verify
            ]
            mock_browser.capture_screenshot_b64.return_value = ""
            mock_browser.get_current_url.return_value = "https://example.com/login"
            mock_browser.get_page_title.return_value = "Login Page"

            agent = WebVeilAgent(max_steps=2, headless=True, provider_name="mock")
            agent.browser = mock_browser

            observed_contexts = []
            def mock_reason(task, world_model, action_history, error_context=None):
                observed_contexts.append(error_context)
                if len(observed_contexts) == 1:
                    return ActionPlan(actions=[BrowserAction(action=ActionType.CLICK, node_id=1)], thought="Try login")
                else:
                    return ActionPlan(actions=[BrowserAction(action=ActionType.DONE)], thought="Stop on error")

            mock_provider = MagicMock()
            mock_provider.provider_name = "mock"
            mock_provider.reason.side_effect = mock_reason
            mock_provider.token_usage.input_tokens = 10
            mock_provider.token_usage.output_tokens = 10
            mock_provider.token_usage.total_calls = 2
            agent.provider = mock_provider
            agent.firewall.execute_validated_action = MagicMock(return_value=True)

            res = agent.run_task("https://example.com/login", "Login to portal", initial_navigate=False)

            self.assertEqual(res["status"], "SUCCESS")
            # First call has None, second call has the verification error context!
            self.assertIsNone(observed_contexts[0])
            self.assertIsNotNone(observed_contexts[1])
            self.assertIn("Verification failed", observed_contexts[1])
            self.assertIn("Invalid credentials", observed_contexts[1])

            # Verify REPLAN stage was emitted
            replan_events = [e for e in agent.state.events if e.stage == AgentStage.REPLAN.value]
            self.assertGreaterEqual(len(replan_events), 1)


if __name__ == "__main__":
    unittest.main()

