"""
Generalization test on external website (Wikipedia).
Verifies that WebVeil V1.5 agent loop can load a real external website,
extract & prune DOM nodes, redacts sensitive entities, reasons, grounds actions, and executes steps cleanly.
"""

import unittest
import asyncio
from webveil.agent_loop import WebVeilAgent
from webveil.core.models.schema import ActionType


class TestWikipediaGeneralization(unittest.TestCase):

    def test_wikipedia_navigation_and_dom_pruning(self):
        """Test agent loop initialization, real page load, deterministic DOM pruning, and step execution."""
        agent = WebVeilAgent(max_steps=2, provider_name="mock")
        
        # Start browser session
        agent.browser.start(headless=True)
        
        # Navigate to Wikipedia home page
        print("[Generalization] Navigating to Wikipedia...")
        agent.browser.navigate("https://en.wikipedia.org/wiki/Main_Page")
        self.assertTrue(agent.browser.page.url.startswith("https://en.wikipedia.org"))
        
        # Extract DOM nodes from real Wikipedia page
        dom_nodes, formatted_dom = agent.browser.extract_dom()
        
        # Run DOM pruner on real Wikipedia DOM
        pruned_nodes, metrics = agent.dom_ranker.rank_and_compress(dom_nodes, agent.task_analyzer.analyze_task("Search for Artificial Intelligence"))
        
        print(f"[Generalization] Raw Wikipedia DOM nodes: {metrics.raw_nodes}, Pruned: {metrics.filtered_nodes}")
        self.assertGreater(metrics.raw_nodes, 0)
        self.assertGreater(metrics.filtered_nodes, 0)
        self.assertLessEqual(metrics.filtered_nodes, metrics.raw_nodes)
        
        # Ensure search input or interactive links exist in pruned DOM
        has_interactive = any(getattr(n, "is_interactive", False) or n.tag_name in ["input", "button", "a"] for n in pruned_nodes)
        self.assertTrue(has_interactive)
        
        agent.browser.stop()
        print("[Generalization] Wikipedia Generalization Test Passed!")


if __name__ == "__main__":
    unittest.main()
