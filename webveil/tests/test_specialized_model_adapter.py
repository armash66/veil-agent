"""
Unit tests for Phase 6: Specialized Model / Local Policy Adapter.
Verifies LocalModelAdapter, DatasetFineTuningExporter, and HybridReasoningRouter.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock

from webveil.core.models.schema import DOMNode, ActionType, SanitizedWorldModel, BrowserAction, ActionPlan
from webveil.datasets.builder import DatasetBuilder
from webveil.models.adapter import LocalModelAdapter
from webveil.models.trainer import DatasetFineTuningExporter
from webveil.models.router import HybridReasoningRouter


class TestSpecializedModelAdapter(unittest.TestCase):

    def test_local_model_adapter_unambiguous_prediction(self):
        """Verify LocalModelAdapter predicts plan locally for unambiguous search task."""
        adapter = LocalModelAdapter(confidence_threshold=0.75)

        world_model = SanitizedWorldModel(
            url="https://store.example.com",
            sanitized_url="https://store.example.com",
            title="Store Home",
            sanitized_dom=[
                DOMNode(node_id=5, tag_name="input", element_type="search", name="q", attributes={"placeholder": "Search catalog"}, is_interactive=True, is_visible=True),
                DOMNode(node_id=6, tag_name="button", text_content="Search", is_interactive=True, is_visible=True),
            ],
            formatted_dom="<input name='q'/>",
        )

        plan = adapter.predict_plan(
            task="Find wireless bluetooth headphones",
            world_model=world_model,
            action_history=[],
        )

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action, ActionType.TYPE)
        self.assertEqual(plan.actions[0].node_id, 5)
        self.assertIn("headphones", plan.actions[0].text.lower())
        self.assertIn("[Local Policy]", plan.thought)

    def test_local_model_adapter_delegation_conditions(self):
        """Verify LocalModelAdapter delegates when error occurred or no matches exist."""
        adapter = LocalModelAdapter(confidence_threshold=0.75)
        world_model = SanitizedWorldModel(
            url="https://store.example.com",
            sanitized_url="https://store.example.com",
            title="Store Home",
            sanitized_dom=[],
            formatted_dom="",
        )

        # Case 1: Error context present
        plan_error = adapter.predict_plan("search item", world_model, [], error_context="Timeout clicking button")
        self.assertIsNone(plan_error)

        # Case 2: Empty DOM / Low confidence
        plan_empty = adapter.predict_plan("complex multi-step checkout workflow", world_model, [])
        self.assertIsNone(plan_empty)

    def test_dataset_fine_tuning_exporter(self):
        """Verify Alpaca, ChatML, and DPO training format exporters."""
        samples = DatasetBuilder().build_curated_sih_benchmark()

        with tempfile.TemporaryDirectory() as tmpdir:
            alpaca_path = os.path.join(tmpdir, "alpaca.json")
            chatml_path = os.path.join(tmpdir, "chatml.jsonl")
            dpo_path = os.path.join(tmpdir, "dpo.jsonl")

            DatasetFineTuningExporter.export_alpaca_format(samples, alpaca_path)
            DatasetFineTuningExporter.export_chatml_format(samples, chatml_path)
            DatasetFineTuningExporter.export_dpo_pairs(samples, dpo_path)

            # Check Alpaca
            with open(alpaca_path, "r", encoding="utf-8") as f:
                alpaca_data = json.load(f)
            self.assertEqual(len(alpaca_data), len(samples))
            self.assertIn("instruction", alpaca_data[0])
            self.assertIn("output", alpaca_data[0])

            # Check ChatML
            with open(chatml_path, "r", encoding="utf-8") as f:
                chatml_lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(chatml_lines), len(samples))
            self.assertIn("messages", chatml_lines[0])
            self.assertEqual(chatml_lines[0]["messages"][0]["role"], "system")

            # Check DPO
            with open(dpo_path, "r", encoding="utf-8") as f:
                dpo_lines = [json.loads(line) for line in f if line.strip()]
            self.assertGreater(len(dpo_lines), 0)
            self.assertIn("chosen", dpo_lines[0])
            self.assertIn("rejected", dpo_lines[0])

    def test_hybrid_reasoning_router(self):
        """Verify HybridReasoningRouter routes locally when confident and remotely when complex."""
        mock_remote = MagicMock()
        mock_remote.provider_name = "mock_gemini"
        mock_remote.reason.return_value = ActionPlan(
            actions=[BrowserAction(action=ActionType.DONE, thought="Remote plan executed")],
            thought="Remote complex reasoning"
        )
        mock_remote.token_usage.input_tokens = 500
        mock_remote.token_usage.output_tokens = 100

        router = HybridReasoningRouter(remote_provider=mock_remote)

        # 1. Unambiguous local task (should route locally)
        local_model = SanitizedWorldModel(
            url="https://portal.com",
            sanitized_url="https://portal.com",
            title="Portal",
            sanitized_dom=[
                DOMNode(node_id=1, tag_name="input", element_type="search", attributes={"placeholder": "Search"}, is_interactive=True, is_visible=True)
            ],
            formatted_dom="<input name='search'/>",
        )

        plan1 = router.reason("Search flight status", local_model, [])
        self.assertEqual(router.local_calls, 1)
        self.assertEqual(router.remote_calls, 0)
        self.assertEqual(mock_remote.reason.call_count, 0)
        self.assertIn("[Local Policy]", plan1.thought)

        # 2. Complex / recovery task (should route remotely)
        plan2 = router.reason("Search flight status", local_model, [], error_context="Action failed")
        self.assertEqual(router.local_calls, 1)
        self.assertEqual(router.remote_calls, 1)
        self.assertEqual(mock_remote.reason.call_count, 1)
        self.assertIn("Remote", plan2.thought)

        stats = router.get_routing_stats()
        self.assertEqual(stats["local_calls"], 1)
        self.assertEqual(stats["remote_calls"], 1)
        self.assertEqual(stats["local_ratio"], 0.5)
        self.assertGreater(stats["estimated_tokens_saved"], 0)


if __name__ == "__main__":
    unittest.main()
