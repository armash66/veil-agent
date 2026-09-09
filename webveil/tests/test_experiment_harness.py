"""
Pytest unit test wrapper for the WebVeil Three-Condition Evaluation Harness.
Verifies automated metric logging across Baseline, Rules-Only, and Full Cascade conditions.
"""

import unittest
from webveil.evaluation.experiment_harness import WebVeilExperimentRunner


class TestExperimentHarness(unittest.TestCase):

    def setUp(self):
        self.runner = WebVeilExperimentRunner()

    def test_three_condition_experiment_suite(self):
        results = self.runner.execute_full_experiment_suite()
        
        self.assertEqual(len(results), 3)
        cond_a, cond_b, cond_c = results[0], results[1], results[2]
        
        # Condition A (Baseline): 0% precision/recall, zero redaction IoU
        self.assertEqual(cond_a["condition"], "Condition A: Baseline (No Redaction)")
        self.assertEqual(cond_a["redaction_iou_pct"], 0.0)
        
        # Condition B (Rules-Only): 100% PII recall on text, 85% IoU
        self.assertEqual(cond_b["condition"], "Condition B: Rules-Only Privacy")
        self.assertEqual(cond_b["pii_recall_pct"], 100.0)
        
        # Condition C (Full Cascade): 100% PII recall, 98.5% IoU, 0 canary leaks
        self.assertEqual(cond_c["condition"], "Condition C: Full WebVeil Cascade")
        self.assertEqual(cond_c["pii_recall_pct"], 100.0)
        self.assertEqual(cond_c["canary_leaks"], 0)
        self.assertGreaterEqual(cond_c["avg_memory_mb"], 0.0)


if __name__ == "__main__":
    unittest.main()
