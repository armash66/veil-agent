"""
Unit tests for Phase 4: Task-Aware DOM Intelligence.
Verifies TaskAwareDOMRanker, ContextCompressor, and ActionPredictor.
"""

import unittest
from webveil.core.models.schema import DOMNode, ActionType, TaskRepresentation
from webveil.core.intelligence.dom_ranker import TaskAwareDOMRanker
from webveil.core.intelligence.context_compressor import ContextCompressor
from webveil.core.intelligence.action_predictor import ActionPredictor


class TestTaskAwareIntelligence(unittest.TestCase):

    def test_task_aware_dom_ranker_features_and_scoring(self):
        """Verify feature extraction and task relevance scoring."""
        ranker = TaskAwareDOMRanker(target_top_k=5)
        task = TaskRepresentation(
            intent="product_search",
            entities=["laptop", "dell"],
            constraints={"ram": "16GB"},
            raw_prompt="Search for Dell laptop with 16GB RAM",
        )

        relevant_input = DOMNode(
            node_id=1,
            tag_name="input",
            element_type="search",
            name="query",
            text_content="",
            attributes={"placeholder": "Search laptop or brand"},
            is_interactive=True,
            is_visible=True,
            bounding_box={"x": 50, "y": 100, "width": 200, "height": 30},
        )

        unrelated_container = DOMNode(
            node_id=2,
            tag_name="div",
            text_content="random sidebar copyright info",
            is_interactive=False,
            is_visible=True,
            bounding_box={"x": 10, "y": 2000, "width": 100, "height": 50},
        )

        hidden_button = DOMNode(
            node_id=3,
            tag_name="button",
            text_content="Submit",
            is_interactive=True,
            is_visible=False,
        )

        score_relevant = ranker.score_node(relevant_input, task)
        score_unrelated = ranker.score_node(unrelated_container, task)
        score_hidden = ranker.score_node(hidden_button, task)

        self.assertGreater(score_relevant, score_unrelated)
        self.assertEqual(score_hidden, 0.0)

        # Rank and compress a list
        ranked, metrics = ranker.rank_and_compress([relevant_input, unrelated_container, hidden_button], task)
        # Only visible nodes with score > 0.05 are retained
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].node_id, 1)

    def test_context_compressor_budget_enforcement(self):
        """Verify context compressor respects token budget limits strictly."""
        compressor = ContextCompressor(max_token_budget=150)

        # Generate 20 mock nodes
        nodes = []
        for i in range(20):
            is_inter = (i < 5)
            nodes.append(DOMNode(
                node_id=i,
                tag_name="button" if is_inter else "p",
                text_content=f"Detailed descriptive text content for element number {i} with metadata",
                is_interactive=is_inter,
                is_visible=True,
            ))

        retained, report = compressor.compress_to_budget(nodes, budget_override=150)

        self.assertLessEqual(report.compressed_tokens, 150)
        self.assertTrue(report.budget_exhausted)
        self.assertGreater(len(retained), 0)
        # Interactive elements should be prioritized
        self.assertTrue(all(n.is_interactive for n in retained[:min(len(retained), 3)]))

    def test_action_predictor_search_and_form(self):
        """Verify action predictor accurately hypothesizes next action."""
        predictor = ActionPredictor()

        task_search = TaskRepresentation(
            intent="product_search",
            entities=["shoes"],
            raw_prompt="find red shoes",
        )

        search_input = DOMNode(
            node_id=12,
            tag_name="input",
            element_type="search",
            value="",
            is_interactive=True,
        )
        search_button = DOMNode(
            node_id=13,
            tag_name="button",
            text_content="Search",
            is_interactive=True,
        )

        # Case 1: Empty search input -> TYPE
        pred1 = predictor.predict_next_action(task_search, [search_input, search_button])
        self.assertEqual(pred1.predicted_action, ActionType.TYPE)
        self.assertEqual(pred1.candidate_node_id, 12)
        self.assertGreater(pred1.confidence, 0.8)

        # Case 2: Search input filled -> CLICK search button
        search_input_filled = DOMNode(
            node_id=12,
            tag_name="input",
            element_type="search",
            value="red shoes",
            is_interactive=True,
        )
        pred2 = predictor.predict_next_action(task_search, [search_input_filled, search_button])
        self.assertEqual(pred2.predicted_action, ActionType.CLICK)
        self.assertEqual(pred2.candidate_node_id, 13)

        # Case 3: Page shows success indicator after several actions -> DONE
        success_node = DOMNode(
            node_id=20,
            tag_name="h2",
            text_content="Your order placed successfully!",
            is_interactive=False,
        )
        pred3 = predictor.predict_next_action(task_search, [success_node], action_count=6)
        self.assertEqual(pred3.predicted_action, ActionType.DONE)


if __name__ == "__main__":
    unittest.main()
