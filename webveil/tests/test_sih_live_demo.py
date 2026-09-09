"""
Unit tests for WebVeil Real SIH Live Demo Driver.
Verifies the end-to-end 5-act demonstration runner executes flawlessly.
"""

import unittest
from webveil.demos.sih_live_demo import SIHLiveDemoRunner


class TestSIHLiveDemo(unittest.TestCase):

    def setUp(self):
        self.runner = SIHLiveDemoRunner()

    def test_sih_live_demo_execution(self):
        """Verify the complete 5-act demo runs and satisfies all SIH criteria."""
        results = self.runner.run_demo(verbose=False)

        # Act 1: Vaulting
        self.assertIn("act_1_vaulting", results)
        self.assertGreaterEqual(results["act_1_vaulting"]["detected"], 1)
        self.assertGreaterEqual(len(results["act_1_vaulting"]["tokens"]), 1)

        # Act 2: Injection defense
        self.assertIn("act_2_injection_defense", results)
        self.assertTrue(results["act_2_injection_defense"]["attack_1_blocked"])
        self.assertTrue(results["act_2_injection_defense"]["attack_2_blocked"])

        # Act 3: Pointer trajectory
        self.assertIn("act_3_pointer", results)
        self.assertGreaterEqual(results["act_3_pointer"]["points_count"], 10)

        # Act 4: Verification
        self.assertIn("act_4_verification", results)
        self.assertEqual(results["act_4_verification"]["status"], "SUCCESS")

        # Act 5: Scorecard
        self.assertIn("act_5_scorecard", results)
        scorecard = results["act_5_scorecard"]
        self.assertGreaterEqual(scorecard["overall_score"], 80.0)
        self.assertEqual(scorecard["adversarial_defense_rate"], 100.0)
        self.assertEqual(scorecard["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
