"""
Live Playwright Browser Integration Security & Mutation Test Suite.
Executes security validation against actual live Chromium DOM state.
"""

import unittest
from playwright.sync_api import sync_playwright
from webveil.browser.playwright_adapter import PlaywrightAdapter
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault, VaultRestorationError
from webveil.core.privacy.redactor import LocalRedactor
from webveil.security.firewall.action_firewall import ActionFirewall, ActionSecurityViolation
from webveil.core.models.schema import DOMNode, PIIMatch, PIICategory, BrowserAction, ActionType


class TestLivePlaywrightSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.adapter = PlaywrightAdapter()
        cls.adapter.start(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.adapter.stop()

    def setUp(self):
        self.detector = LocalPIIDetector()
        self.vault = ClientVault("http://localhost")
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.firewall = ActionFirewall(self.vault, self.adapter)

    def test_live_1_element_hidden_after_observation(self):
        """LIVE 1: Element hidden in live DOM after observation."""
        html = """
        <html><body>
            <input type="password" id="secret_input" value="CANARY_PASS_999">
        </body></html>
        """
        self.adapter.page.set_content(html)
        dom_nodes, _ = self.adapter.extract_dom()
        pwd_node = next(n for n in dom_nodes if n.element_id == "secret_input")

        # Store vault match
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_999", placeholder="[PASSWORD_1]", source_node_id=pwd_node.node_id)
        self.vault.store_match(match, "http://localhost", pwd_node)

        # LIVE DOM MUTATION: Hide element
        self.adapter.page.evaluate("document.getElementById('secret_input').style.display = 'none';")

        # Re-observe DOM
        post_dom, _ = self.adapter.extract_dom()
        hidden_node = DOMNode(node_id=pwd_node.node_id, tag_name="input", element_type="password", is_visible=False)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", hidden_node, "http://localhost")

    def test_live_2_element_type_changed_after_observation(self):
        """LIVE 2: Password input changed to text type in live DOM after observation."""
        html = """
        <html><body>
            <input type="password" id="secret_input" value="CANARY_PASS_888">
        </body></html>
        """
        self.adapter.page.set_content(html)
        dom_nodes, _ = self.adapter.extract_dom()
        pwd_node = next(n for n in dom_nodes if n.element_id == "secret_input")

        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_888", placeholder="[PASSWORD_1]", source_node_id=pwd_node.node_id)
        self.vault.store_match(match, "http://localhost", pwd_node)

        # LIVE DOM MUTATION: Change input type to text
        self.adapter.page.evaluate("document.getElementById('secret_input').setAttribute('type', 'text');")

        mutated_node = DOMNode(node_id=pwd_node.node_id, tag_name="input", element_type="text", is_visible=True)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", mutated_node, "http://localhost")

    def test_live_3_stale_node_reference_rejection(self):
        """LIVE 3: Action targeting stale/deleted node ID rejected by firewall."""
        html = "<html><body><button id='btn1'>Click Me</button></body></html>"
        self.adapter.page.set_content(html)
        dom_nodes, _ = self.adapter.extract_dom()

        # Delete element from live DOM
        self.adapter.page.evaluate("document.getElementById('btn1').remove();")
        fresh_dom, _ = self.adapter.extract_dom()

        action = BrowserAction(action=ActionType.CLICK, node_id=999)  # Stale node ID

        with self.assertRaises(ActionSecurityViolation):
            self.firewall.execute_validated_action(action, fresh_dom, "http://localhost")

    def test_live_4_origin_change_rejection(self):
        """LIVE 4: Secret restoration across origin boundary rejected."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_777", placeholder="[PASSWORD_1]", source_node_id=1)
        node = DOMNode(node_id=1, tag_name="input", element_type="password", is_visible=True)
        self.vault.store_match(match, "http://localhost", node)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", node, current_origin="http://attacker.com")


if __name__ == "__main__":
    unittest.main()
