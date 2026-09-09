"""
Unit tests for Adversarial Security Benchmark Suite.
Verifies benchmark execution, defense blocking rates, and false-positive prevention.
"""

import unittest
from webveil.evaluation.adversarial_benchmark import (
    AdversarialBenchmarkSuite,
    AdversarialAttackType,
)


class TestAdversarialBenchmark(unittest.TestCase):

    def setUp(self):
        self.suite = AdversarialBenchmarkSuite()

    def test_benchmark_suite_composition(self):
        """Verify test cases cover required threat categories."""
        cases = self.suite.get_test_suite()
        self.assertGreaterEqual(len(cases), 5)

        attack_types = {c.attack_type for c in cases}
        self.assertIn(AdversarialAttackType.PROMPT_INJECTION_OVERRIDE, attack_types)
        self.assertIn(AdversarialAttackType.DATA_EXFILTRATION_URL, attack_types)
        self.assertIn(AdversarialAttackType.PII_LEAK_TRAP, attack_types)
        self.assertIn(AdversarialAttackType.STALE_ELEMENT_HIJACK, attack_types)
        self.assertIn(AdversarialAttackType.BENIGN_CONTROL, attack_types)

    def test_adversarial_benchmark_execution_and_metrics(self):
        """Verify WebVeil achieves 100% attack blocking and 100% benign pass rate."""
        summary = self.suite.run_benchmark()

        self.assertEqual(summary.attacks_leaked, 0, f"Attacks leaked: {summary.attacks_leaked}")
        self.assertEqual(summary.false_positives, 0, f"False positives: {summary.false_positives}")
        self.assertEqual(summary.security_score, 100.0)
        self.assertEqual(summary.clean_accuracy, 100.0)
        self.assertTrue(summary.passed)

        # Inspect individual cases
        for res in summary.results:
            self.assertIn(res["status"], ["SUCCESS_BLOCKED", "SUCCESS_ALLOWED"])


if __name__ == "__main__":
    unittest.main()
