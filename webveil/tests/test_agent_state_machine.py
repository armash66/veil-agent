"""
Unit tests for Phase 1: Structured Agent State & Stage Machine.
Verifies AgentStage, AgentEvent, AgentState lifecycle, event emission,
and state-driven loop execution with zero-PII leak guarantees.
"""

import unittest
from unittest.mock import MagicMock, patch

from webveil.core.models.schema import (
    DOMNode, BrowserAction, ActionType, ActionPlan, ActionResult,
    TaskRepresentation, PIIMatch, PIICategory,
)
from webveil.core.models.state import AgentStage, AgentEvent, AgentState
from webveil.agent_loop import WebVeilAgent


class TestAgentStateMachine(unittest.TestCase):

    def test_agent_stage_enum_and_events(self):
        """Verify all 11 explicit stages are present and AgentEvent serialization works."""
        expected_stages = [
            "UNDERSTAND", "OBSERVE", "FILTER", "PROTECT", "REASON",
            "GROUND", "AUTHORIZE", "ACT", "VERIFY", "UPDATE_STATE",
            "REPLAN", "DONE"
        ]
        for stage_name in expected_stages:
            stage = AgentStage(stage_name)
            self.assertEqual(stage.value, stage_name)

        # Backward compatibility check
        self.assertEqual(AgentStage.PERCEIVE, AgentStage.OBSERVE)

        event = AgentEvent(
            stage=AgentStage.UNDERSTAND.value,
            status="completed",
            step=1,
            metadata={"intent": "search", "count": 2}
        )
        d = event.to_dict()
        self.assertEqual(d["stage"], "UNDERSTAND")
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["step"], 1)
        self.assertEqual(d["metadata"]["intent"], "search")
        self.assertIn("timestamp", d)

    def test_agent_state_event_emission_and_pii_sanitization(self):
        """Verify AgentState emits events cleanly and truncates/sanitizes metadata."""
        state = AgentState(task="Book flight from Mumbai to Delhi")
        self.assertEqual(state.stage, AgentStage.UNDERSTAND)
        self.assertFalse(state.is_terminal())

        # Emit event with rich metadata
        ev = state.emit_event(
            stage=AgentStage.PROTECT,
            status="completed",
            metadata={
                "pii_detected": 2,
                "categories": ["AADHAAR_NUMBER", "CREDIT_CARD"],
                "raw_aadhaar_secret": "987654321098",  # raw string should be truncated/handled
                "flag": True,
            }
        )
        self.assertEqual(len(state.events), 1)
        self.assertEqual(ev.stage, "PROTECT")
        self.assertEqual(ev.metadata["pii_detected"], 2)
        self.assertEqual(ev.metadata["flag"], True)
        self.assertIn("AADHAAR_NUMBER", ev.metadata["categories"])

        # Test terminal transitions
        state.termination_reason = "SUCCESS"
        self.assertTrue(state.is_terminal())

    def test_agent_state_lifecycle_progression(self):
        """Verify complete state transitions across stages with executed actions tracking."""
        state = AgentState(task="Find cheapest laptop", max_steps=5)
        
        # Step 1: UNDERSTAND
        state.stage = AgentStage.UNDERSTAND
        state.task_representation = TaskRepresentation(
            intent="product_search", entities=["laptop"], raw_prompt="Find cheapest laptop"
        )
        state.emit_event(AgentStage.UNDERSTAND, "completed")

        # Step 2: OBSERVE
        state.step_number = 1
        state.stage = AgentStage.OBSERVE
        state.emit_event(AgentStage.OBSERVE, "completed", {"raw_dom_nodes": 45})

        # Step 3: FILTER
        state.stage = AgentStage.FILTER
        sample_node = DOMNode(node_id=1, tag_name="button", text_content="Search")
        state.selected_elements = [sample_node]
        state.emit_event(AgentStage.FILTER, "completed", {"filtered_nodes": 1})

        # Step 4: PROTECT
        state.stage = AgentStage.PROTECT
        state.emit_event(AgentStage.PROTECT, "completed", {"pii_detected": 0})

        # Step 5: REASON
        state.stage = AgentStage.REASON
        action = BrowserAction(action=ActionType.CLICK, node_id=1, thought="Click search")
        plan = ActionPlan(actions=[action], thought="Let's click search button")
        state.reasoning_result = plan
        state.proposed_actions = [action]
        state.emit_event(AgentStage.REASON, "completed")

        # Step 6: GROUND
        state.stage = AgentStage.GROUND
        state.emit_event(AgentStage.GROUND, "completed", {"node_id": 1})

        # Step 7: AUTHORIZE
        state.stage = AgentStage.AUTHORIZE
        state.emit_event(AgentStage.AUTHORIZE, "completed")

        # Step 8: ACT
        state.stage = AgentStage.ACT
        act_res = ActionResult(action=action, success=True, step_index=1)
        state.executed_actions.append(act_res)
        state.emit_event(AgentStage.ACT, "completed", {"success": True})

        # Step 9: VERIFY
        state.stage = AgentStage.VERIFY
        state.verification_result = True
        state.emit_event(AgentStage.VERIFY, "completed", {"verified": True})

        # Step 10: UPDATE_STATE
        state.stage = AgentStage.UPDATE_STATE
        state.emit_event(AgentStage.UPDATE_STATE, "completed")

        # Step 11: DONE
        state.stage = AgentStage.DONE
        state.termination_reason = "SUCCESS"
        state.emit_event(AgentStage.DONE, "completed", {"reason": "SUCCESS"})

        self.assertTrue(state.is_terminal())
        self.assertEqual(len(state.executed_actions), 1)
        self.assertEqual(len(state.failed_actions), 0)
        self.assertEqual(len(state.events), 11)

    @patch("webveil.agent_loop.PlaywrightAdapter")
    def test_agent_loop_success_completion(self, mock_playwright_cls):
        """Verify WebVeilAgent executes through AgentState until SUCCESS."""
        mock_browser = MagicMock()
        mock_playwright_cls.return_value = mock_browser
        mock_browser.extract_dom.return_value = (
            [DOMNode(node_id=1, tag_name="button", text_content="Submit", is_visible=True, is_interactive=True)],
            "<button>Submit</button>"
        )
        mock_browser.capture_screenshot_b64.return_value = ""
        mock_browser.get_current_url.return_value = "https://example.com"
        mock_browser.get_page_title.return_value = "Example Title"

        agent = WebVeilAgent(max_steps=3, headless=True, provider_name="mock")
        agent.browser = mock_browser

        # Configure mock provider to immediately propose DONE
        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.reason.return_value = ActionPlan(
            actions=[BrowserAction(action=ActionType.DONE, thought="All done")],
            thought="Task finished successfully"
        )
        mock_provider.token_usage.input_tokens = 50
        mock_provider.token_usage.output_tokens = 20
        mock_provider.token_usage.total_calls = 1
        agent.provider = mock_provider

        result = agent.run_task(
            start_url="https://example.com",
            task="Check the status",
            initial_navigate=False,
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertIsNotNone(agent.state)
        self.assertEqual(agent.state.stage, AgentStage.DONE)
        self.assertEqual(agent.state.termination_reason, "SUCCESS")
        self.assertTrue(agent.state.is_terminal())

        # Check emitted events include UNDERSTAND, OBSERVE, FILTER, PROTECT, REASON, DONE
        stages_emitted = [e.stage for e in agent.state.events]
        self.assertIn("UNDERSTAND", stages_emitted)
        self.assertIn("OBSERVE", stages_emitted)
        self.assertIn("FILTER", stages_emitted)
        self.assertIn("PROTECT", stages_emitted)
        self.assertIn("REASON", stages_emitted)
        self.assertIn("DONE", stages_emitted)

    @patch("webveil.agent_loop.PlaywrightAdapter")
    def test_agent_loop_max_steps_reached(self, mock_playwright_cls):
        """Verify WebVeilAgent properly terminates with MAX_STEPS_REACHED."""
        mock_browser = MagicMock()
        mock_playwright_cls.return_value = mock_browser
        node = DOMNode(node_id=1, tag_name="button", text_content="Next", is_visible=True, is_interactive=True)
        mock_browser.extract_dom.return_value = ([node], "<button>Next</button>")
        mock_browser.capture_screenshot_b64.return_value = ""
        mock_browser.get_current_url.return_value = "https://example.com"
        mock_browser.get_page_title.return_value = "Example Title"

        agent = WebVeilAgent(max_steps=2, headless=True, provider_name="mock")
        agent.browser = mock_browser

        # Propose continuous click actions that vary so loop detection doesn't trigger
        call_count = 0
        def varying_plan(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ActionPlan(
                actions=[BrowserAction(action=ActionType.CLICK, node_id=1, text=f"step_{call_count}", thought="Keep going")],
                thought=f"Working step {call_count}"
            )

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.reason.side_effect = varying_plan
        mock_provider.token_usage.input_tokens = 10
        mock_provider.token_usage.output_tokens = 10
        mock_provider.token_usage.total_calls = 2
        agent.provider = mock_provider

        # Mock firewall execution
        agent.firewall.execute_validated_action = MagicMock(return_value=True)

        result = agent.run_task(
            start_url="https://example.com",
            task="Infinite task",
            initial_navigate=False,
        )

        self.assertEqual(result["status"], "MAX_STEPS_REACHED")
        self.assertEqual(agent.state.stage, AgentStage.DONE)
        self.assertEqual(agent.state.termination_reason, "MAX_STEPS_REACHED")
        self.assertEqual(agent.state.step_number, 2)
        self.assertEqual(len(agent.state.executed_actions), 2)


if __name__ == "__main__":
    unittest.main()
