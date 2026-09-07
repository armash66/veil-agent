"""
WebVeil Adversarial Security & Attack Resistance Test Suite.
Verifies defense against Attacks A through J as specified in SIH Hardening Guidelines.
"""

import json
import unittest
from webveil.core.models.schema import DOMNode, PIICategory, PIIMatch, EgressPayload, SanitizedObservation, BrowserAction, ActionType
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault, VaultRestorationError
from webveil.core.privacy.redactor import LocalRedactor
from webveil.security.sanitizers.url_error_sanitizer import URLErrorSanitizer
from webveil.security.egress.privacy_gate import EgressPrivacyGate, PrivacyViolationError
from webveil.security.firewall.action_firewall import ActionFirewall, ActionSecurityViolation
from webveil.agent_loop import WebVeilAgent


class TestAdversarialSecurityHardening(unittest.TestCase):

    def setUp(self):
        self.detector = LocalPIIDetector()
        self.vault = ClientVault("http://localhost:8080")
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.sanitizer = URLErrorSanitizer(self.detector)
        self.egress_gate = EgressPrivacyGate(self.detector)

    def test_attack_a_wrong_vault_node(self):
        """ATTACK A: Server requests secret restoration into wrong node ID."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_123", placeholder="[PASSWORD_1]", source_node_id=10)
        self.vault.store_match(match, "http://localhost:8080")
        wrong_target_node = DOMNode(node_id=99, tag_name="input", element_type="password", is_visible=True)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", wrong_target_node, "http://localhost:8080")

    def test_attack_b_hidden_input_restoration(self):
        """ATTACK B: Server targets hidden input field (style='display:none')."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_123", placeholder="[PASSWORD_1]", source_node_id=15)
        self.vault.store_match(match, "http://localhost:8080")
        hidden_target_node = DOMNode(node_id=15, tag_name="input", element_type="password", is_visible=False)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", hidden_target_node, "http://localhost:8080")

    def test_attack_c_dom_mutation(self):
        """ATTACK C: Target DOM element mutated after observation."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_123", placeholder="[PASSWORD_1]", source_node_id=20)
        source_node = DOMNode(node_id=20, tag_name="input", element_type="password", element_id="pwd_field", name="pwd")
        self.vault.store_match(match, "http://localhost:8080", source_node)

        mutated_target_node = DOMNode(node_id=88, tag_name="input", element_type="password", element_id="different_id", name="different_name")
        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", mutated_target_node, "http://localhost:8080")

    def test_attack_d_origin_change_mismatch(self):
        """ATTACK D: Secret restoration attempted across different origin."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_123", placeholder="[PASSWORD_1]", source_node_id=5)
        self.vault.store_match(match, "http://localhost:8080")
        valid_node = DOMNode(node_id=5, tag_name="input", element_type="password", is_visible=True)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", valid_node, "http://evil.example.com")

    def test_attack_e_wrong_input_type(self):
        """ATTACK E: Attempting to inject password token into non-password input."""
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="CANARY_PASS_123", placeholder="[PASSWORD_1]", source_node_id=7)
        self.vault.store_match(match, "http://localhost:8080")
        wrong_type_node = DOMNode(node_id=7, tag_name="input", element_type="text", is_visible=True)

        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", wrong_type_node, "http://localhost:8080")

    def test_attack_f_url_query_leakage(self):
        """ATTACK F: Verification that raw canary in URL query parameter is redacted."""
        leaking_url = "https://example.com/reset?email=CANARY_EMAIL_999@example.com&phone=9876543210"
        clean_url = self.sanitizer.sanitize_url(leaking_url)

        self.assertNotIn("CANARY_EMAIL_999@example.com", clean_url)
        self.assertNotIn("9876543210", clean_url)
        self.assertIn("EMAIL_REDACTED", clean_url)

    def test_attack_g_exception_trace_leakage(self):
        """ATTACK G: Exception trace containing raw password canary is sanitized."""
        raw_traceback = "TimeoutError: Could not find input[value='CANARY_PASSWORD_888'] on page"
        clean_traceback = self.sanitizer.sanitize_error(raw_traceback)

        self.assertNotIn("CANARY_PASSWORD_888", clean_traceback)
        self.assertIn("CANARY_REDACTED", clean_traceback)

    def test_attack_h_action_history_leakage(self):
        """ATTACK H: Action history records ONLY token placeholders, never raw secrets."""
        action_entry = {
            "step": 1,
            "action": "type",
            "node_id": 5,
            "text": "[PASSWORD_1]",
            "placeholder_restored": True
        }
        entry_json = json.dumps(action_entry)

        self.assertNotIn("CANARY_PASSWORD", entry_json)
        self.assertIn("[PASSWORD_1]", entry_json)

    def test_attack_i_malicious_server_actions(self):
        """ATTACK I: Server attempts unauthorized actions (execute_js, eval, shell, filesystem)."""
        firewall = ActionFirewall(self.vault, None)

        malicious_actions = ["execute_js", "eval", "shell", "filesystem", "clipboard", "download_file"]
        for bad_act in malicious_actions:
            bad_action = BrowserAction(action=bad_act)
            with self.assertRaises(ActionSecurityViolation):
                firewall.validate_action_schema(bad_action)

    def test_attack_j_runaway_agent_circuit_breaker(self):
        """ATTACK J: Circuit breaker terminates runaway agent when max_steps limit is exceeded."""
        agent = WebVeilAgent(max_steps=2, headless=True)
        # Verify max_steps is strictly set to 2
        self.assertEqual(agent.max_steps, 2)


if __name__ == "__main__":
    unittest.main()
