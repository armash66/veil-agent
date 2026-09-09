"""
Unit tests for WebVeil Agent Memory System.
Tests ZeroPIIMemoryGuard, EpisodicMemory, and Semantic SiteKnowledgeStore.
"""

import unittest
from webveil.core.memory.guard import ZeroPIIMemoryGuard, MemoryPrivacyViolation
from webveil.core.memory.episodic import EpisodicMemory, TaskEpisodeRecord
from webveil.core.memory.site_knowledge import SiteKnowledgeStore, SitePattern


class TestAgentMemory(unittest.TestCase):

    def setUp(self):
        self.guard = ZeroPIIMemoryGuard()
        self.episodic = EpisodicMemory(guard=self.guard)
        self.site_knowledge = SiteKnowledgeStore(guard=self.guard)

    def test_memory_guard_blocks_pii(self):
        """Verify memory guard prevents saving raw secrets or PII."""
        # Clean text passes
        self.guard.assert_clean("Search for mechanical keyboard on Amazon")

        # PII text fails
        with self.assertRaises(MemoryPrivacyViolation):
            self.guard.assert_clean("User email is john.doe@secretcorp.com and ssn is 123-45-6789")

    def test_episodic_memory_record_and_search(self):
        """Verify recording and querying sanitized task episodes."""
        ep1 = TaskEpisodeRecord(
            session_id="sess-001",
            task_goal="Find cheap laptops on Amazon",
            domains_visited=["amazon.in"],
            action_summary=["Navigated to Amazon", "Typed laptop", "Filtered by price"],
            outcome_status="SUCCESS",
        )
        ep2 = TaskEpisodeRecord(
            session_id="sess-002",
            task_goal="Deploy NextJS app to Vercel",
            domains_visited=["vercel.com"],
            action_summary=["Opened dashboard", "Clicked new project"],
            outcome_status="SUCCESS",
        )
        ep3 = TaskEpisodeRecord(
            session_id="sess-003",
            task_goal="Book flight tickets to Delhi",
            domains_visited=["makemytrip.com"],
            action_summary=["Search failed due to timeout"],
            outcome_status="FAILURE",
        )

        self.episodic.record_episode(ep1)
        self.episodic.record_episode(ep2)
        self.episodic.record_episode(ep3)

        # Search by keyword
        laptop_res = self.episodic.search_episodes("laptop")
        self.assertEqual(len(laptop_res), 1)
        self.assertEqual(laptop_res[0].session_id, "sess-001")

        # Search by domain
        vercel_res = self.episodic.search_episodes("deploy", domain="vercel.com")
        self.assertEqual(len(vercel_res), 1)
        self.assertEqual(vercel_res[0].session_id, "sess-002")

        # Success rate calculations
        self.assertEqual(self.episodic.get_success_rate(domain="amazon.in"), 1.0)
        self.assertEqual(self.episodic.get_success_rate(domain="makemytrip.com"), 0.0)
        self.assertEqual(self.episodic.get_success_rate(), 0.67)

    def test_episodic_memory_rejects_unredacted_pii(self):
        """Verify attempt to record episode with raw PII raises MemoryPrivacyViolation."""
        poisoned_ep = TaskEpisodeRecord(
            session_id="sess-bad",
            task_goal="Submit user Aadhaar 2345 6789 0123 for verification",
            domains_visited=["gov.in"],
            action_summary=["Typed Aadhaar into input"],
            outcome_status="SUCCESS",
        )
        with self.assertRaises(MemoryPrivacyViolation):
            self.episodic.record_episode(poisoned_ep)

    def test_site_knowledge_store_patterns(self):
        """Verify pre-seeded site knowledge and pattern learning."""
        # Query default pre-seeded patterns
        gh_search = self.site_knowledge.lookup_pattern("github.com", "search")
        self.assertIsNotNone(gh_search)
        self.assertIn("input[name='q']", gh_search.selector_hints)

        wiki_search = self.site_knowledge.lookup_pattern("en.wikipedia.org", "search")
        self.assertIsNotNone(wiki_search)
        self.assertEqual(wiki_search.common_path, "/w/index.php")

        # Register custom site pattern
        new_pattern = SitePattern(
            domain="custom-shop.com",
            action_type="checkout",
            selector_hints=["button#pay-now", "div.checkout-btn"],
            common_path="/cart/checkout",
            notes="Checkout requires 2 clicks",
        )
        self.site_knowledge.learn_pattern(new_pattern)

        retrieved = self.site_knowledge.lookup_pattern("custom-shop.com", "checkout")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.common_path, "/cart/checkout")

    def test_continuation_preserves_active_task_intent(self):
        """
        Regression Test (AWS -> ISRO Continuation):
        TASK: 'Open ISRO website'
        CURRENT PAGE: AWS Console (https://console.aws.amazon.com)
        USER SAYS: 'ok do it'
        EXPECTED: Continues active task to navigate to ISRO, NOT reinterpreting AWS Console as a new goal!
        """
        from unittest.mock import MagicMock, patch
        from webveil.agent_loop import WebVeilAgent
        from webveil.core.models.schema import DOMNode, BrowserAction, ActionType, ActionPlan
        from webveil.core.memory.working_memory import AgentWorkingMemory

        wm = AgentWorkingMemory()
        # 1. Initial user task
        wm.set_task("Open ISRO website")
        self.assertEqual(wm.original_task, "Open ISRO website")

        # 2. Page loads AWS Console
        wm.update_environment_state(
            url="https://eu-north-1.console.aws.amazon.com/console/home",
            title="AWS Management Console",
            dom_nodes_count=224,
        )
        self.assertEqual(wm.current_url, "https://eu-north-1.console.aws.amazon.com/console/home")

        # 3. User says "ok do it"
        wm.set_task("ok do it")
        # Assert active persistent task intent is preserved
        self.assertEqual(wm.original_task, "Open ISRO website")

        # 4. End-to-end agent loop verification
        with patch("webveil.agent_loop.PlaywrightAdapter") as mock_pw_cls:
            mock_browser = MagicMock()
            mock_pw_cls.return_value = mock_browser

            aws_node = DOMNode(
                node_id=1, tag_name="a", text_content="Sign In to AWS Console",
                is_visible=True, is_interactive=True
            )
            mock_browser.extract_dom.return_value = ([aws_node], "<a>Sign In to AWS Console</a>")
            mock_browser.capture_screenshot_b64.return_value = ""
            mock_browser.get_current_url.return_value = "https://eu-north-1.console.aws.amazon.com/console/home"
            mock_browser.get_page_title.return_value = "AWS Management Console"

            agent = WebVeilAgent(max_steps=2, headless=True, provider_name="mock")
            agent.browser = mock_browser

            # First turn: set original task
            agent.working_memory.set_task("Open ISRO website")

            proposed_task_passed = None
            def mock_reason(task, world_model, action_history, error_context=None):
                nonlocal proposed_task_passed
                proposed_task_passed = task
                return ActionPlan(
                    actions=[BrowserAction(action=ActionType.NAVIGATE, url="https://www.isro.gov.in")],
                    thought="Navigating to ISRO website as requested"
                )

            mock_provider = MagicMock()
            mock_provider.provider_name = "mock"
            mock_provider.reason.side_effect = mock_reason
            mock_provider.token_usage.input_tokens = 20
            mock_provider.token_usage.output_tokens = 20
            mock_provider.token_usage.total_calls = 1
            agent.provider = mock_provider

            # Execute continuation prompt
            result = agent.run_task(
                start_url="https://eu-north-1.console.aws.amazon.com/console/home",
                task="ok do it",
                initial_navigate=False,
            )

            # Confirm agent used the preserved ISRO task intent, not AWS sign-in
            self.assertEqual(proposed_task_passed, "Open ISRO website")
            self.assertEqual(agent.working_memory.original_task, "Open ISRO website")
            self.assertEqual(agent.state.task, "Open ISRO website")

    def test_working_memory_lifecycle_and_failures(self):
        """Verify subgoal transitions, structured failure recording, and verification memory."""
        from webveil.core.memory.working_memory import AgentWorkingMemory, FailureType, GoalStatus

        wm = AgentWorkingMemory()
        wm.set_task("Complete Multi-Step Checkout")

        g1 = wm.add_subgoal("Enter delivery address", "Address verified")
        g2 = wm.add_subgoal("Confirm payment", "Receipt generated")

        self.assertEqual(wm.get_active_goal().goal_id, "goal_1")
        wm.advance_goal_on_success()
        self.assertEqual(wm.get_active_goal().goal_id, "goal_2")

        # Record a structured failure
        fail_rec = wm.record_failure(
            failure_type=FailureType.STALE_TARGET,
            step_index=2,
            details="Node [15] detached during form submission",
        )
        self.assertEqual(fail_rec.failure_type, FailureType.STALE_TARGET)
        self.assertEqual(len(wm.get_recent_failures()), 1)

        # Record verification
        wm.record_verification(
            step_index=2,
            expected_state="Order confirmed banner",
            actual_state="Error banner: Card declined",
            verified=False,
            confidence=0.25,
            reasons=["Card declined error"],
        )
        self.assertEqual(len(wm.verification_history), 1)
        self.assertFalse(wm.verification_history[0].verified)


if __name__ == "__main__":
    unittest.main()

