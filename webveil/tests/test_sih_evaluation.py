"""
Unit tests for Unified SIH Evaluation Engine.
Tests computation of 5 weighted SIH evaluation criteria and report generation.
"""

import unittest
from webveil.evaluation.sih_evaluator import SIHEvaluationEngine, SIHEvaluationSummary


class TestSIHEvaluation(unittest.TestCase):

    def setUp(self):
        self.engine = SIHEvaluationEngine()

    def test_full_sih_evaluation_run(self):
        """Verify SIH evaluation computes all 5 official criteria and achieves passing score."""
        summary = self.engine.run_full_evaluation()

        self.assertIsInstance(summary, SIHEvaluationSummary)
        self.assertGreaterEqual(summary.overall_score, 80.0)
        self.assertEqual(summary.status, "PASSED")
        self.assertEqual(summary.redaction_precision, 100.0)
        self.assertEqual(summary.adversarial_defense_rate, 100.0)
        self.assertGreaterEqual(summary.visual_accuracy, 90.0)
        self.assertGreaterEqual(summary.pii_f1_score, 80.0)

    def test_report_generation(self):
        """Verify Markdown executive report format."""
        summary = self.engine.run_full_evaluation()
        md = summary.generate_markdown_report()

        self.assertIn("# WebVeil SIH 2026 Evaluation Report", md)
        self.assertIn("Visual Context Accuracy", md)
        self.assertIn("Sensitive / PII Detection F1", md)
        self.assertIn("Redaction Precision", md)
        self.assertIn("Client Resource Footprint", md)
        self.assertIn("End-to-End Latency", md)
        self.assertIn("Adversarial Attack Blocking Rate", md)

        data = summary.to_dict()
        self.assertIn("overall_score", data)
        self.assertIn("peak_memory_mb", data)


if __name__ == "__main__":
    unittest.main()
