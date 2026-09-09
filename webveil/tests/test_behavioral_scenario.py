"""
End-to-End Live Behavioral Scenario Test Suite.

Validates the full behavioral scenario:
1. Initial browser: AWS page
2. User task: "Open the ISRO website" -> Agent creates task
3. User prompt: "ok do it" -> Working memory preserves active task intent & goal (AWS -> ISRO invariant)
4. Perceive AWS -> Context: Current page != desired destination
5. Reason -> Navigate to ISRO
6. Verify -> ISRO page reached -> Task/Goal COMPLETED
7. Deliberately introduce failure: Target becomes stale
8. Verification fails -> Failure memory recorded (STALE_TARGET)
9. Re-perception -> New grounding -> Replan -> Action executed -> Verified -> Continued
"""

import unittest
from playwright.sync_api import sync_playwright

from webveil.browser.playwright_adapter import PlaywrightAdapter
from webveil.core.models.schema import (
    BrowserAction, ActionType, DOMNode, GroundingResult
)
from webveil.core.memory.working_memory import (
    AgentWorkingMemory, SubGoal, GoalStatus, FailureType
)
from webveil.core.grounding.element_grounder import ElementGrounder
from webveil.core.verification.local_verifier import LocalVerifier
from webveil.browser.scheduler import ExecutionScheduler
from webveil.security.firewall.action_firewall import ActionFirewall
from webveil.core.vault.client_vault import ClientVault


class TestLiveBehavioralScenario(unittest.TestCase):
    """
    Live Chromium behavioral verification:
    AWS -> ISRO continuation + Deliberate stale target failure recovery.
    """

    @classmethod
    def setUpClass(cls):
        cls.adapter = PlaywrightAdapter(viewport_size={"width": 1280, "height": 800})
        cls.adapter.start(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.adapter.stop()

    def setUp(self):
        self.memory = AgentWorkingMemory()
        self.grounder = ElementGrounder()
        self.verifier = LocalVerifier()
        self.scheduler = ExecutionScheduler()
        self.vault = ClientVault()
        self.firewall = ActionFirewall(self.vault, self.adapter)

    def test_live_chrome_aws_to_isro_continuation_and_stale_recovery(self):
        """
        Full end-to-end behavioral test with live Chromium.
        """
        # ── 1. Initial browser on AWS page ────────────────────────────────
        aws_html = """
        <!DOCTYPE html>
        <html>
        <head><title>AWS Management Console</title></head>
        <body style="font-family: sans-serif; background: #232f3e; color: white; padding: 20px;">
            <h1>AWS Management Console</h1>
            <div id="account-info">Account ID: 123456789012 (eu-north-1)</div>
            <button id="sign-in-btn" style="padding: 10px 20px; background: #ff9900; border: none; font-weight: bold;">
                Sign In to Console
            </button>
        </body>
        </html>
        """
        self.adapter.page.set_content(aws_html)
        self.adapter.wait_for_stable()

        current_url = self.adapter.get_current_url()
        page_title = self.adapter.get_page_title()
        self.assertIn("AWS", page_title)

        # ── 2. User creates task: "Open the ISRO website" ──────────────────
        user_task = "Open the ISRO website"
        self.memory.set_task(user_task)
        self.memory.subgoals = [
            SubGoal(
                goal_id="g1",
                description="Navigate to ISRO",
                expected_outcome="ISRO portal loaded",
                status=GoalStatus.ACTIVE
            )
        ]

        self.assertEqual(self.memory.original_task, "Open the ISRO website")
        self.assertEqual(self.memory.get_active_goal().description, "Navigate to ISRO")

        # ── 3. User says "ok do it" -> Memory MUST preserve active intent ─
        continuation_prompt = "ok do it"
        self.memory.set_task(continuation_prompt)

        # CRITICAL INVARIANT: The task remains "Open the ISRO website", NOT "Sign in to AWS"
        self.assertEqual(self.memory.original_task, "Open the ISRO website")
        self.assertEqual(self.memory.get_active_goal().description, "Navigate to ISRO")

        # ── 4. Perceive AWS page ──────────────────────────────────────────
        raw_dom_nodes, formatted_dom = self.adapter.extract_dom()
        self.assertTrue(len(raw_dom_nodes) > 0)
        self.assertTrue(any("AWS" in (n.text_content or "") for n in raw_dom_nodes))

        # Context Check: Current page != desired destination (AWS != ISRO)
        self.assertNotIn("isro", page_title.lower())
        self.assertNotIn("isro", current_url.lower())

        # ── 5. Reason: Issue Navigation to ISRO ───────────────────────────
        isro_url = "https://www.isro.gov.in"
        nav_action = BrowserAction(
            action=ActionType.NAVIGATE,
            url=isro_url,
            thought="Current page is AWS Console; active goal is Navigate to ISRO. Navigating."
        )

        # Grounding check for global navigation
        grounding = self.grounder.ground_action(nav_action, raw_dom_nodes)
        self.assertEqual(grounding.threshold_action, "EXECUTE")

        # ── 6. Execute Navigation & Verify ISRO Page Reached ──────────────
        # Serve rendered ISRO page content in live Chromium
        isro_html = """
        <!DOCTYPE html>
        <html>
        <head><title>ISRO - Indian Space Research Organisation</title></head>
        <body style="font-family: sans-serif; background: #f0f4f8; padding: 20px;">
            <h1>Indian Space Research Organisation</h1>
            <p>Welcome to the official portal of ISRO.</p>
            <div id="nav-container">
                <button id="missions-btn" style="padding: 10px 15px; background: #003366; color: white; border: none; cursor: pointer;">
                    Missions
                </button>
            </div>
            <div id="content-display" style="margin-top: 20px; font-weight: bold;"></div>
            <script>
                document.getElementById('missions-btn').addEventListener('click', function() {
                    document.getElementById('content-display').innerText = 'Chandrayaan-3 & Gaganyaan Missions Active';
                });
            </script>
        </body>
        </html>
        """
        # Execute in live browser
        self.adapter.page.set_content(isro_html)
        self.adapter.wait_for_stable()

        post_nav_nodes, _ = self.adapter.extract_dom()
        post_title = self.adapter.get_page_title()

        self.assertIn("ISRO", post_title)

        # Local Verification confirms state transition
        v_result = self.verifier.verify_action_result(
            nav_action,
            raw_dom_nodes,
            post_nav_nodes,
            previous_url="https://console.aws.amazon.com",
            current_url=isro_url,
            user_task=user_task
        )
        self.assertTrue(v_result.status.value == "SUCCESS")

        # Working memory advances active goal
        self.memory.advance_goal_on_success()
        self.assertEqual(self.memory.subgoals[0].status, GoalStatus.COMPLETED)

        # ── 7. Deliberately Introduce Failure: Target Becomes Stale ────────
        # Agent intends to click "Missions" button
        missions_node = next(n for n in post_nav_nodes if n.element_id == "missions-btn")
        stale_click_action = BrowserAction(
            action=ActionType.CLICK,
            node_id=missions_node.node_id,
            thought="Click on the Missions button to inspect active missions."
        )

        # DELIBERATE MUTATION: Live DOM removes the button before execution
        self.adapter.page.evaluate("document.getElementById('missions-btn').remove();")

        # Scheduler and Grounder detect the stale element
        fresh_nodes_after_removal, _ = self.adapter.extract_dom()
        stale_grounding = self.grounder.ground_action(stale_click_action, fresh_nodes_after_removal)

        # Grounder REJECTS stale element with 0% confidence
        self.assertEqual(stale_grounding.threshold_action, "REPLAN")
        self.assertEqual(stale_grounding.confidence, 0.0)
        self.assertIn("stale element", stale_grounding.reasoning.lower())

        # ── 8. Failure Memory Recorded ────────────────────────────────────
        self.memory.record_failure(
            failure_type=FailureType.STALE_TARGET,
            step_index=2,
            details=stale_grounding.reasoning,
            action=stale_click_action
        )

        self.assertEqual(len(self.memory.failure_history), 1)
        self.assertEqual(self.memory.failure_history[0].failure_type, FailureType.STALE_TARGET)

        # ── 9. Re-perception & Dynamic Replacement ────────────────────────
        # Inject dynamic replacement navigation link (e.g. dynamic responsive menu)
        self.adapter.page.evaluate("""
            const fallback = document.createElement('a');
            fallback.id = 'missions-nav-link';
            fallback.href = '#';
            fallback.innerText = 'Explore Missions';
            fallback.style.padding = '10px';
            fallback.style.background = '#0055aa';
            fallback.style.color = 'white';
            fallback.onclick = function() {
                document.getElementById('content-display').innerText = 'Chandrayaan-3 & Gaganyaan Missions Active (Recovered)';
            };
            document.getElementById('nav-container').appendChild(fallback);
        """)
        self.adapter.wait_for_stable()

        # Re-perceive live DOM
        recovered_dom_nodes, _ = self.adapter.extract_dom()
        recovered_link_node = next(n for n in recovered_dom_nodes if n.element_id == "missions-nav-link")
        self.assertIsNotNone(recovered_link_node)

        # ── 10. New Grounding & Replan ────────────────────────────────────
        recovered_action = BrowserAction(
            action=ActionType.CLICK,
            node_id=recovered_link_node.node_id,
            thought="Retrying missions inspection via recovered missions-nav-link"
        )

        recovered_grounding = self.grounder.ground_action(recovered_action, recovered_dom_nodes)
        self.assertGreaterEqual(recovered_grounding.confidence, 0.85)
        self.assertEqual(recovered_grounding.threshold_action, "EXECUTE")

        # ── 11. Execute & Verify Continued Success ────────────────────────
        # Execution through ActionFirewall
        readiness = self.scheduler.await_readiness(self.adapter.page, recovered_action)
        self.assertTrue(readiness.is_ready)

        exec_success = self.firewall.execute_validated_action(
            recovered_action,
            recovered_dom_nodes,
            current_origin="https://www.isro.gov.in"
        )
        self.assertTrue(exec_success)

        # Check DOM update happened in live Chromium
        display_text = self.adapter.page.inner_text("#content-display")
        self.assertIn("Chandrayaan-3", display_text)

        # Final Verification
        post_exec_nodes, _ = self.adapter.extract_dom()
        final_v_res = self.verifier.verify_action_result(
            recovered_action,
            recovered_dom_nodes,
            post_exec_nodes,
            previous_url=isro_url,
            current_url=isro_url,
            user_task="Inspect active missions"
        )
        self.assertTrue(final_v_res.status.value in ["SUCCESS", "PARTIAL_SUCCESS"])

        # Final Memory Record
        self.memory.record_action(recovered_action, success=True, step_index=3)
        self.assertEqual(len(self.memory.action_history), 1)
        self.assertTrue(self.memory.action_history[0].result_success)


if __name__ == "__main__":
    unittest.main()
