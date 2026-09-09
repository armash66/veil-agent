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


if __name__ == "__main__":
    unittest.main()
