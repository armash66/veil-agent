"""
Adversarial Security Test Suite for Extension JS Components:
- IsolatedClientVault (6-point restoration validation)
- ActionFirewall (whitelist, step cap, rate limit, node freshness, visibility guard, atomic batch rejection)

Executes live Chromium tests using Playwright to evaluate extension/content_script.js directly in the browser DOM environment.
"""

import os
import unittest
from playwright.sync_api import sync_playwright


CONTENT_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../extension/content_script.js")
)


class TestExtensionJSSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        with open(CONTENT_SCRIPT_PATH, "r", encoding="utf-8") as f:
            cls.content_script_code = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def _setup_page_with_script(self, html_content: str):
        self.page.set_content(html_content)
        self.page.evaluate(self.content_script_code)

    # ═══════════════════════════════════════════════════════════
    # 1. ISOLATED CLIENT VAULT ADVERSARIAL TESTS
    # ═══════════════════════════════════════════════════════════

    def test_vault_1_origin_mismatch_rejected(self):
        """VAULT 1: Secret restoration across origin boundary must be rejected."""
        html = """
        <html><body>
            <input type="password" id="pwd" name="password" value="SECRET_PASS_123">
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                const vault = new hook.IsolatedClientVault();
                const node = document.getElementById('pwd');
                
                const token = vault.storeSecret('SECRET_PASS_123', node, 'https://legitimate-bank.com');
                
                try {
                    vault.restoreSecret(token, node, 'https://attacker-site.com');
                    return { rejected: false };
                } catch (e) {
                    return { rejected: true, message: e.message };
                }
            }
        """)

        self.assertTrue(result["rejected"])
        self.assertIn("Origin mismatch", result["message"])

    def test_vault_2_target_node_mismatch_rejected(self):
        """VAULT 2: Secret restoration targeting a different node than source must be rejected."""
        html = """
        <html><body>
            <input type="password" id="source_pwd" name="password" value="SECRET_PASS_123">
            <input type="text" id="target_input" name="exfil" value="">
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                const vault = new hook.IsolatedClientVault();
                const sourceNode = document.getElementById('source_pwd');
                const targetNode = document.getElementById('target_input');
                
                const token = vault.storeSecret('SECRET_PASS_123', sourceNode, window.location.origin);
                
                try {
                    vault.restoreSecret(token, targetNode, window.location.origin);
                    return { rejected: false };
                } catch (e) {
                    return { rejected: true, message: e.message };
                }
            }
        """)

        self.assertTrue(result["rejected"])
        self.assertIn("Target node mismatch", result["message"])

    def test_vault_3_hidden_opacity_zero_1px_rejected(self):
        """VAULT 3: Target node hidden via display:none, visibility:hidden, opacity:0, or 1px dimensions must be rejected."""
        html = """
        <html><body>
            <input type="password" id="display_none" style="display:none" value="P1">
            <input type="password" id="vis_hidden" style="visibility:hidden" value="P2">
            <input type="password" id="opacity_zero" style="opacity:0" value="P3">
            <input type="password" id="one_pixel" style="width:1px;height:1px" value="P4">
        </body></html>
        """
        self._setup_page_with_script(html)

        for element_id in ["display_none", "vis_hidden", "opacity_zero", "one_pixel"]:
            result = self.page.evaluate(f"""
                () => {{
                    const hook = window.__WebVeil_TestHook;
                    const vault = new hook.IsolatedClientVault();
                    const node = document.getElementById('{element_id}');
                    
                    const token = vault.storeSecret('SECRET_PASS_123', node, window.location.origin);
                    
                    try {{
                        vault.restoreSecret(token, node, window.location.origin);
                        return {{ rejected: false }};
                    }} catch (e) {{
                        return {{ rejected: true, message: e.message }};
                    }}
                }}
            """)

            self.assertTrue(result["rejected"], f"Failed to reject hidden element: {element_id}")
            self.assertIn("hidden or 0-size", result["message"])

    def test_vault_4_fingerprint_alteration_rejected(self):
        """VAULT 4: Node whose ID, name, type, or tag is altered post-observation must be rejected."""
        html = """
        <html><body>
            <input type="password" id="pwd_field" name="password" value="SECRET_PASS">
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                const vault = new hook.IsolatedClientVault();
                const node = document.getElementById('pwd_field');
                
                const token = vault.storeSecret('SECRET_PASS', node, window.location.origin);
                
                // Mutate attribute to alter fingerprint
                node.setAttribute('type', 'text');
                
                try {
                    vault.restoreSecret(token, node, window.location.origin);
                    return { rejected: false };
                } catch (e) {
                    return { rejected: true, message: e.message };
                }
            }
        """)

        self.assertTrue(result["rejected"])
        self.assertIn("fingerprint altered", result["message"])

    def test_vault_5_stale_detached_node_rejected(self):
        """VAULT 5: Restoration attempt when original node reference was garbage collected / detached."""
        html = """
        <html><body>
            <div id="container"><input type="password" id="pwd_temp" value="TEMP_SECRET"></div>
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                const vault = new hook.IsolatedClientVault();
                let node = document.getElementById('pwd_temp');
                
                const token = vault.storeSecret('TEMP_SECRET', node, window.location.origin);
                
                // Remove node from DOM
                node.remove();
                
                try {
                    vault.restoreSecret(token, node, window.location.origin);
                    return { rejected: false };
                } catch (e) {
                    return { rejected: true, message: e.message };
                }
            }
        """)

        self.assertTrue(result["rejected"])

    # ═══════════════════════════════════════════════════════════
    # 2. ACTION FIREWALL ADVERSARIAL TESTS
    # ═══════════════════════════════════════════════════════════

    def test_firewall_1_unknown_malformed_action_rejected(self):
        """FIREWALL 1: Unknown or malformed action type must be rejected immediately."""
        html = "<html><body><button id='btn'>Click</button></body></html>"
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                hook.resetFirewall();
                
                const r1 = hook.executeAction({ action: 'DROP_TABLE', node_id: 0 });
                const r2 = hook.executeAction({});
                const r3 = hook.executeAction(null);
                
                return { r1, r2, r3 };
            }
        """)

        self.assertFalse(result["r1"]["success"])
        self.assertIn("not in the allowed whitelist", result["r1"]["detail"])
        self.assertFalse(result["r2"]["success"])
        self.assertIn("No action specified", result["r2"]["detail"])
        self.assertFalse(result["r3"]["success"])

    def test_firewall_2_unobserved_out_of_bounds_node_rejected(self):
        """FIREWALL 2: Action targeting node_id out of bounds or not in DOM must be rejected."""
        html = "<html><body><button id='btn0'>Button 0</button></body></html>"
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                hook.resetFirewall();
                
                return hook.executeAction({ action: 'CLICK', node_id: 999 });
            }
        """)

        self.assertFalse(result["success"])
        self.assertIn("stale or out of range", result["detail"])

    def test_firewall_3_step_cap_16th_action_rejected(self):
        """FIREWALL 3: 16th non-trivial action in a session must be rejected (max 15 step cap)."""
        html = """
        <html><body>
            <button id='b0'>Click</button>
            <input type='text' id='i1'>
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                hook.resetFirewall();
                
                const results = [];
                // Execute 15 valid actions with bypassRateLimiter to test step cap isolation
                for (let i = 0; i < 15; i++) {
                    hook.bypassRateLimiter();
                    const res = hook.executeAction({ action: 'CLICK', node_id: 0 });
                    results.push(res);
                }
                
                // Attempt 16th action
                hook.bypassRateLimiter();
                const step16 = hook.executeAction({ action: 'CLICK', node_id: 0 });
                
                return { step15_ok: results[14].success, step16 };
            }
        """)

        self.assertTrue(result["step15_ok"])
        self.assertFalse(result["step16"]["success"])
        self.assertIn("Step cap exceeded", result["step16"]["detail"])

    def test_firewall_4_rate_limiter_throttled(self):
        """FIREWALL 4: Actions executed faster than 500ms apart must be throttled/rejected."""
        html = "<html><body><button id='b0'>Button</button></body></html>"
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                hook.resetFirewall();
                
                const res1 = hook.executeAction({ action: 'CLICK', node_id: 0 });
                // Immediate second action (<500ms)
                const res2 = hook.executeAction({ action: 'CLICK', node_id: 0 });
                
                return { res1, res2 };
            }
        """)

        self.assertTrue(result["res1"]["success"])
        self.assertFalse(result["res2"]["success"])
        self.assertIn("Rate limit", result["res2"]["detail"])

    def test_firewall_5_batch_action_atomic_rejection(self):
        """FIREWALL 5: Batched multi-action where 1 action is invalid must result in total batch rejection (no partial execution)."""
        html = """
        <html><body>
            <input type="text" id="target" value="initial">
            <button id="btn">Click</button>
        </body></html>
        """
        self._setup_page_with_script(html)

        result = self.page.evaluate("""
            () => {
                const hook = window.__WebVeil_TestHook;
                hook.resetFirewall();
                
                const targetInput = document.getElementById('target');
                
                // Batch: Action 1 is valid TYPE into target, Action 2 is invalid node_id 999
                const batch = [
                    { action: 'TYPE', node_id: 0, text: 'MODIFIED_TEXT' },
                    { action: 'CLICK', node_id: 999 }
                ];
                
                const batchResult = hook.executeAction(batch);
                
                // Verify target input was NOT mutated (Action 1 was NOT executed)
                const textAfter = targetInput.value;
                
                return { batchResult, textAfter };
            }
        """)

        self.assertFalse(result["batchResult"]["success"])
        self.assertIn("FIREWALL BATCH REJECT", result["batchResult"]["detail"])
        # Action 1 must NOT have executed
        self.assertEqual(result["textAfter"], "initial")


if __name__ == "__main__":
    unittest.main()
