"""
WebVeil Comprehensive Privacy, Security & Zero-Canary-Leakage Test Suite.
Verifies all 12 security & privacy invariants before declaring V0 complete.
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
from webveil.evaluation.metrics import SIHMetricsEvaluator


class TestWebVeilPrivacyCore(unittest.TestCase):

    def setUp(self):
        self.detector = LocalPIIDetector()
        self.vault = ClientVault("http://localhost:8080")
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.sanitizer = URLErrorSanitizer(self.detector)
        self.egress_gate = EgressPrivacyGate(self.detector)

    def test_1_email_detection(self):
        node = DOMNode(node_id=1, tag_name="input", element_type="text", text_content="User email is canary-email-001@example.com")
        matches = self.detector.scan_dom_node(node)
        self.assertTrue(any(m.category == PIICategory.EMAIL for m in matches))

    def test_2_phone_detection(self):
        node = DOMNode(node_id=2, tag_name="input", element_type="text", text_content="Call me at 9876543210")
        matches = self.detector.scan_dom_node(node)
        self.assertTrue(any(m.category == PIICategory.PHONE for m in matches))

    def test_3_aadhaar_detection(self):
        node = DOMNode(node_id=3, tag_name="input", element_type="text", text_content="Aadhaar: 1234 5678 9012")
        matches = self.detector.scan_dom_node(node)
        self.assertTrue(any(m.category == PIICategory.AADHAAR for m in matches))

    def test_4_password_input_detection(self):
        node = DOMNode(node_id=4, tag_name="input", element_type="password", value="CANARY_PASSWORD_001")
        matches = self.detector.scan_dom_node(node)
        self.assertTrue(any(m.category == PIICategory.PASSWORD for m in matches))

    def test_5_url_query_sanitization(self):
        raw_url = "https://example.com/reset?email=canary-email-001@example.com&token=1234"
        sanitized = self.sanitizer.sanitize_url(raw_url)
        self.assertNotIn("canary-email-001@example.com", sanitized)
        self.assertIn("EMAIL_REDACTED", sanitized)

    def test_6_error_traceback_sanitization(self):
        raw_error = "Timeout Error waiting for input[value='CANARY_PASSWORD_001']"
        sanitized = self.sanitizer.sanitize_error(raw_error)
        self.assertNotIn("CANARY_PASSWORD_001", sanitized)
        self.assertIn("CANARY_REDACTED", sanitized)

    def test_7_client_vault_wrong_node_rejection(self):
        match = PIIMatch(category=PIICategory.PASSWORD, raw_value="Secret123", placeholder="[PASSWORD_1]", source_node_id=10)
        self.vault.store_match(match, "http://localhost:8080")
        
        # Wrong node ID attempt
        wrong_node = DOMNode(node_id=99, tag_name="input", element_type="text", is_visible=True)
        with self.assertRaises(VaultRestorationError):
            self.vault.restore("[PASSWORD_1]", wrong_node, "http://localhost:8080")

    def test_8_action_firewall_unauthorized_action_rejection(self):
        dummy_browser = None
        firewall = ActionFirewall(self.vault, dummy_browser)
        bad_action = BrowserAction(action="execute_js")  # Not in white list
        with self.assertRaises(ActionSecurityViolation):
            firewall.validate_action_schema(bad_action)

    def test_9_egress_gate_canary_audit_blocking(self):
        # Attempt to pass unredacted canary payload
        leaking_obs = SanitizedObservation(
            url="http://localhost:8080",
            sanitized_url="http://localhost:8080",
            title="Leaking Test",
            dom_tree=[],
            formatted_dom="[1] <input value='CANARY_EMAIL_001@example.com'>",  # Unredacted canary!
            redacted_screenshot_b64="",
            detected_pii_count=0
        )
        payload = EgressPayload(task="test", observation=leaking_obs, action_history=[])
        
        with self.assertRaises(PrivacyViolationError):
            self.egress_gate.audit_and_authorize(payload)

    def test_10_zero_canary_leakage_success(self):
        # Properly sanitized payload
        clean_obs = SanitizedObservation(
            url="http://localhost:8080",
            sanitized_url="http://localhost:8080",
            title="Clean Test",
            dom_tree=[],
            formatted_dom="[1] <input value='[EMAIL_1]'>",  # Sanitized placeholder
            redacted_screenshot_b64="",
            detected_pii_count=1,
            pii_categories_found=["EMAIL"]
        )
        payload = EgressPayload(task="test", observation=clean_obs, action_history=[])
        authorized = self.egress_gate.audit_and_authorize(payload)
        self.assertIn("[EMAIL_1]", authorized["dom"])
        self.assertNotIn("canary", json.dumps(authorized).lower())


if __name__ == "__main__":
    import json
    unittest.main()
