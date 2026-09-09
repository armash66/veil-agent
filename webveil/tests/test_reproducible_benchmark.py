"""
Unit tests for Reproducible Benchmark & Full Ablation Suite.
Verifies all 8 ablation stages, metric calculations, zero leakage enforcement,
and markdown summary rendering.
"""

import unittest
from webveil.evaluation.reproducible_benchmark import ReproducibleBenchmark, AblationMetrics


class TestReproducibleBenchmark(unittest.TestCase):

    def setUp(self):
        self.benchmark = ReproducibleBenchmark()

    def test_environment_generation(self):
        """Verify benchmark environment synthesizes expected mixed archetypes and canaries."""
        env = self.benchmark.generate_benchmark_environment()
        nodes = env["nodes"]
        canaries = env["canaries"]
        ocr_regions = env["ocr_regions"]

        self.assertGreaterEqual(len(nodes), 200)
        self.assertEqual(len(canaries), 4)
        self.assertGreaterEqual(len(ocr_regions), 2)

        # Check ambiguous non-PII node presence
        aws_node = next((n for n in nodes if "AWS Account:" in n.text_content), None)
        self.assertIsNotNone(aws_node)

    def test_run_all_ablations(self):
        """Verify all 8 progressive ablation conditions execute and show monotonic improvements."""
        results = self.benchmark.run_all_ablations()
        self.assertEqual(len(results), 8)

        # Stage 1 (Baseline): Has leaks, 0% PII recall
        baseline = results[0]
        self.assertEqual(baseline.stage_name, "1. Baseline (Raw DOM)")
        self.assertGreater(baseline.privacy_leaks, 0)
        self.assertEqual(baseline.pii_recall_pct, 0.0)

        # Stage 3 (+ OCR): Visual accuracy improves
        ocr_stage = results[2]
        self.assertGreater(ocr_stage.visual_accuracy_pct, baseline.visual_accuracy_pct)

        # Stage 5 (+ Visual Privacy): Privacy leaks become 0
        privacy_stage = results[4]
        self.assertEqual(privacy_stage.privacy_leaks, 0)
        self.assertEqual(privacy_stage.pii_recall_pct, 100.0)
        # Without contextual intel, false positives exist
        self.assertGreater(privacy_stage.false_positives, 0)

        # Stage 6 (+ Task Filtering): Token reduction > 50%
        filtering_stage = results[5]
        self.assertGreater(filtering_stage.token_reduction_pct, 50.0)

        # Stage 7 (+ Contextual Intel): False positives drop to 0
        context_stage = results[6]
        self.assertEqual(context_stage.false_positives, 0)
        self.assertEqual(context_stage.pii_precision_pct, 100.0)

        # Stage 8 (+ Adaptive Fast-Path): Fast latency while maintaining precision and safety
        adaptive_stage = results[7]
        self.assertEqual(adaptive_stage.privacy_leaks, 0)
        self.assertLess(adaptive_stage.latency_ms, ocr_stage.latency_ms)

    def test_markdown_table_rendering(self):
        """Verify benchmark produces a valid, readable Markdown table for judging/documentation."""
        results = self.benchmark.run_all_ablations()
        md_table = self.benchmark.format_markdown_table(results)

        self.assertIn("| Progressive Pipeline Layer |", md_table)
        self.assertIn("1. Baseline (Raw DOM)", md_table)
        self.assertIn("8. + Adaptive Fast-Path", md_table)
        self.assertIn("0 (Safe)", md_table)


if __name__ == "__main__":
    unittest.main()
