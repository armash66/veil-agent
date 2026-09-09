"""
Unit tests for Local Context Manager.
Tests minimal context selection, task-aware DOM compression reporting,
provenance tagging, and working memory integration.
"""

import unittest
from webveil.core.models.schema import DOMNode, SanitizedWorldModel, TaskRepresentation
from webveil.core.memory.working_memory import AgentWorkingMemory, FailureType
from webveil.core.context.manager import LocalContextManager


class TestContextManager(unittest.TestCase):

    def setUp(self):
        self.manager = LocalContextManager(max_selected_elements=10)

    def test_context_selection_and_compression_stats(self):
        """Verify context manager selects relevant nodes and calculates token savings."""
        # 50 background nodes + 3 interactive target nodes
        nodes = []
        for i in range(1, 51):
            nodes.append(DOMNode(
                node_id=i, tag_name="p", text_content=f"Irrelevant background body paragraph text {i}",
                is_visible=True, is_interactive=False
            ))

        # Target interactive elements
        nodes.append(DOMNode(
            node_id=51, tag_name="input", text_content="",
            attributes={"placeholder": "Search query", "name": "q"},
            is_visible=True, is_interactive=True
        ))
        nodes.append(DOMNode(
            node_id=52, tag_name="button", text_content="Search Flights",
            attributes={"type": "submit"},
            is_visible=True, is_interactive=True
        ))

        world_model = SanitizedWorldModel(
            url="https://travel.example.com",
            sanitized_url="https://travel.example.com",
            title="Flight Booking Portal",
            sanitized_dom=nodes,
            formatted_dom="",
            a11y_summary="Search button role=button",
            ocr_summary="",
            visual_summary="1 card container",
        )

        task_rep = TaskRepresentation(
            intent="flight_search",
            entities=["flights", "search"],
            raw_prompt="Search for flights to Mumbai",
        )

        wm = AgentWorkingMemory()
        wm.set_task("Search for flights to Mumbai", task_rep)
        wm.record_failure(FailureType.TIMEOUT, step_index=1, details="Search button slow to respond")

        payload = self.manager.select_context(
            task="Search for flights to Mumbai",
            world_model=world_model,
            working_memory=wm,
            task_rep=task_rep,
        )

        # Assertions
        self.assertEqual(payload.task, "Search for flights to Mumbai")
        self.assertIn("flight_search", payload.active_goal)
        self.assertLessEqual(len(payload.selected_dom_nodes), 10)
        self.assertIn("Search Flights", payload.formatted_dom)

        # Check compression statistics
        stats = payload.compression_stats
        self.assertEqual(stats.raw_nodes_count, 52)
        self.assertEqual(stats.selected_nodes_count, len(payload.selected_dom_nodes))
        self.assertGreater(stats.compression_ratio_pct, 40.0)
        self.assertGreater(stats.estimated_raw_tokens, stats.estimated_selected_tokens)

        # Check provenance map
        self.assertEqual(payload.provenance_map["task"], "user_instruction")
        self.assertEqual(payload.provenance_map["active_goal"], "working_memory_planner")
        self.assertEqual(payload.provenance_map["url"], "browser_navigation")

        # Check recent failures passed to context
        self.assertEqual(len(payload.recent_failures), 1)
        self.assertIn("TIMEOUT", payload.recent_failures[0])


if __name__ == "__main__":
    unittest.main()
