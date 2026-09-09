"""
Unit tests for Phase 5: Browser-Agent Datasets.
Verifies DatasetSample serialization, DatasetBuilder benchmark generation,
DatasetLoader partitioning, and JSONL export.
"""

import os
import tempfile
import unittest

from webveil.core.models.schema import DOMNode, BrowserAction, ActionType, TextRegion, PIIMatch, PIICategory
from webveil.datasets.schema import DatasetSample
from webveil.datasets.builder import DatasetBuilder
from webveil.datasets.loader import DatasetLoader


class TestDatasetInfrastructure(unittest.TestCase):

    def test_dataset_sample_serialization(self):
        """Verify DatasetSample to_dict and from_dict round-trip."""
        sample = DatasetSample(
            sample_id="test_001",
            domain="ecommerce",
            instruction="Search for camera",
            initial_url="https://store.example.com",
            dom_snapshot=[
                DOMNode(node_id=1, tag_name="input", element_type="search", text_content="Search", is_interactive=True)
            ],
            ocr_regions=[
                TextRegion(text="Deals of the day", bounding_box={"x": 10, "y": 20, "width": 100, "height": 30})
            ],
            ground_truth_actions=[
                BrowserAction(action=ActionType.TYPE, node_id=1, text="camera", thought="Type camera")
            ],
            ground_truth_pii=[
                PIIMatch(category=PIICategory.SECRET, raw_value="CANARY_01", placeholder="[SECRET_1]")
            ],
            expected_target_node_id=1,
            difficulty="easy",
        )

        d = sample.to_dict()
        reconstructed = DatasetSample.from_dict(d)

        self.assertEqual(reconstructed.sample_id, "test_001")
        self.assertEqual(reconstructed.domain, "ecommerce")
        self.assertEqual(len(reconstructed.dom_snapshot), 1)
        self.assertEqual(len(reconstructed.ocr_regions), 1)
        self.assertEqual(len(reconstructed.ground_truth_actions), 1)
        self.assertEqual(len(reconstructed.ground_truth_pii), 1)
        self.assertEqual(reconstructed.ground_truth_pii[0].category, PIICategory.SECRET)

    def test_curated_sih_benchmark_builder(self):
        """Verify DatasetBuilder creates valid curated SIH benchmark samples."""
        builder = DatasetBuilder()
        samples = builder.build_curated_sih_benchmark()

        self.assertGreaterEqual(len(samples), 5)
        domains = {s.domain for s in samples}
        self.assertIn("ecommerce", domains)
        self.assertIn("banking", domains)
        self.assertIn("aws_console", domains)
        self.assertIn("travel", domains)
        self.assertIn("adversarial", domains)

        # Verify all samples pass validation
        for s in samples:
            self.assertTrue(builder.validate_sample(s))

    def test_dataset_loader_splitting_and_filtering(self):
        """Verify train/val/test splitting, filtering, and instruction-tuning pairs generation."""
        builder = DatasetBuilder()
        samples = builder.build_curated_sih_benchmark()

        # Splitting
        split = DatasetLoader.split_dataset(samples, train_ratio=0.60, val_ratio=0.20)
        self.assertGreater(len(split.train), 0)
        self.assertGreater(len(split.val), 0)
        self.assertGreater(len(split.test), 0)
        self.assertEqual(split.summary()["total_count"], len(samples))

        # Filtering by domain
        banking_tasks = DatasetLoader.filter_by_domain(samples, "banking")
        self.assertEqual(len(banking_tasks), 1)
        self.assertEqual(banking_tasks[0].domain, "banking")

        # Filtering by PII presence
        pii_tasks = DatasetLoader.filter_pii_tasks(samples)
        self.assertEqual(len(pii_tasks), 1)
        self.assertEqual(pii_tasks[0].sample_id, "sih_bank_002")

        # Instruction-tuning pairs
        pairs = DatasetLoader.to_fine_tuning_pairs(samples)
        self.assertEqual(len(pairs), len(samples))
        self.assertIn("Task:", pairs[0]["prompt"])
        self.assertIn("Action:", pairs[0]["completion"])

    def test_jsonl_persistence_roundtrip(self):
        """Verify saving and loading dataset samples from JSONL files."""
        builder = DatasetBuilder()
        samples = builder.build_curated_sih_benchmark()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as tf:
            temp_path = tf.name

        try:
            DatasetLoader.save_jsonl(samples, temp_path)
            loaded = DatasetLoader.load_jsonl(temp_path)
            self.assertEqual(len(loaded), len(samples))
            self.assertEqual(loaded[0].sample_id, samples[0].sample_id)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
