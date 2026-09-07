"""
Unit tests for Phase 3 Local Intelligence Layer.
Verifies Local NLP TaskAnalyzer, Task-Aware DOMRanker, LocalPIINerEngine, and ElementGrounder.
"""

import unittest
from webveil.core.models.schema import DOMNode, BrowserAction, ActionType, PIICategory
from webveil.core.nlp.task_analyzer import TaskAnalyzer
from webveil.core.observation.dom_ranker import DOMRanker
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.privacy.ner_detector import LocalPIINerEngine
from webveil.core.grounding.element_grounder import ElementGrounder


class TestPhase3LocalIntelligence(unittest.TestCase):

    def setUp(self):
        self.task_analyzer = TaskAnalyzer()
        self.dom_ranker = DOMRanker(target_top_k=5)
        self.detector = LocalPIIDetector()
        self.ner_engine = LocalPIINerEngine(self.detector)
        self.grounder = ElementGrounder()

    def test_local_task_analyzer(self):
        prompt = "Find three laptops under ₹80000 with 16GB RAM and tell me the cheapest"
        rep = self.task_analyzer.analyze_task(prompt)

        self.assertEqual(rep.intent, "product_search")
        self.assertIn("laptop", rep.entities)
        self.assertEqual(rep.constraints.get("price_max"), 80000)
        self.assertEqual(rep.constraints.get("ram"), "16GB")
        self.assertEqual(rep.count, 3)
        self.assertEqual(rep.objective, "minimum_price")

    def test_dom_ranker_compression(self):
        prompt = "Find three laptops"
        task_rep = self.task_analyzer.analyze_task(prompt)

        # Generate 100 mock DOM nodes
        nodes = []
        for i in range(100):
            is_input = (i == 15)
            nodes.append(DOMNode(
                node_id=i,
                tag_name="input" if is_input else "div",
                element_type="text" if is_input else "",
                text_content="laptop search input" if is_input else f"random container {i}",
                is_interactive=is_input,
                is_visible=True,
            ))

        ranked, metrics = self.dom_ranker.rank_and_compress(nodes, task_rep)

        self.assertEqual(metrics.raw_nodes, 100)
        self.assertEqual(metrics.filtered_nodes, 5)
        self.assertEqual(metrics.compression_ratio, 95.0)
        # Search input node 15 must be retained in top-K
        self.assertTrue(any(n.node_id == 15 for n in ranked))

    def test_pii_ner_deterministic_precedence(self):
        node = DOMNode(
            node_id=1,
            tag_name="input",
            element_type="password",
            value="CANARY_SECRET_123",
            text_content="Enter John Doe password",
            is_interactive=True,
        )

        decisions = self.ner_engine.detect_and_fuse(node, "http://localhost")
        self.assertTrue(len(decisions) > 0)
        # Deterministic password match must have confidence = 1.0
        pwd_d = next(d for d in decisions if d.entity_type == "PASSWORD")
        self.assertEqual(pwd_d.confidence, 1.0)
        self.assertIn("metadata", pwd_d.sources)

    def test_element_grounding_thresholds(self):
        nodes = [
            DOMNode(node_id=5, tag_name="button", text_content="Submit", is_interactive=True, is_visible=True),
        ]

        action_execute = BrowserAction(action=ActionType.CLICK, node_id=5, thought="Clicking submit")
        g1 = self.grounder.ground_action(action_execute, nodes)
        self.assertGreaterEqual(g1.confidence, 0.85)
        self.assertEqual(g1.threshold_action, "EXECUTE")

        action_replan = BrowserAction(action=ActionType.CLICK, node_id=999, thought="Clicking missing node")
        g2 = self.grounder.ground_action(action_replan, nodes)
        self.assertEqual(g2.confidence, 0.0)
        self.assertEqual(g2.threshold_action, "REPLAN")


if __name__ == "__main__":
    unittest.main()
