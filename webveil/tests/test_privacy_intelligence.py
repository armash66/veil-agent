"""
Unit tests for Contextual Privacy Intelligence Engine.
Tests entity disambiguation, false-positive reduction, and policy actions (KEEP vs TOKENIZE vs BLOCK).
"""

import unittest
from webveil.core.models.schema import DOMNode, PIIMatch, PIICategory
from webveil.core.privacy.intelligence import (
    ContextualPrivacyIntelligence,
    PrivacyAction,
)


class TestPrivacyIntelligence(unittest.TestCase):

    def setUp(self):
        self.intelligence = ContextualPrivacyIntelligence()

    def test_aws_account_id_disambiguation(self):
        """Verify 12-digit number in AWS Console context is identified as Account ID and KEPT."""
        candidate = PIIMatch(
            category=PIICategory.AADHAAR,  # Regex candidate
            raw_value="123456789012",
            placeholder="[AADHAAR_1]",
            source_node_id=1,
            context="Account ID: 123456789012",
        )
        node = DOMNode(node_id=1, tag_name="span", text_content="Account ID: 123456789012")

        decision = self.intelligence.evaluate_candidate(
            candidate=candidate,
            context_str="Account ID: 123456789012",
            node=node,
            domain="https://console.aws.amazon.com",
            user_task="Check EC2 instances on account 123456789012",
        )

        self.assertEqual(decision.action, PrivacyAction.KEEP)
        self.assertEqual(decision.classified_entity, "AWS_ACCOUNT_ID")
        self.assertGreaterEqual(decision.confidence, 0.90)

    def test_order_id_disambiguation(self):
        """Verify 12-digit number in e-commerce context is identified as Order ID and KEPT."""
        candidate = PIIMatch(
            category=PIICategory.AADHAAR,
            raw_value="404123456789",
            placeholder="[AADHAAR_1]",
            source_node_id=2,
            context="Order #404123456789",
        )
        node = DOMNode(node_id=2, tag_name="div", text_content="Order #404123456789")

        decision = self.intelligence.evaluate_candidate(
            candidate=candidate,
            context_str="Order #404123456789",
            node=node,
            domain="https://amazon.in",
            user_task="Track my order 404123456789",
        )

        self.assertEqual(decision.action, PrivacyAction.KEEP)
        self.assertEqual(decision.classified_entity, "ORDER_ID")

    def test_aadhaar_kyc_disambiguation(self):
        """Verify 12-digit number in banking/KYC context is classified as Aadhaar and TOKENIZED."""
        candidate = PIIMatch(
            category=PIICategory.AADHAAR,
            raw_value="234567890123",
            placeholder="[AADHAAR_1]",
            source_node_id=3,
            context="Enter Aadhaar Number",
        )
        node = DOMNode(node_id=3, tag_name="input", element_type="text", attributes={"name": "aadhaar", "placeholder": "Enter 12-digit UIDAI number"})

        decision = self.intelligence.evaluate_candidate(
            candidate=candidate,
            context_str="Enter Aadhaar Number",
            node=node,
            domain="https://kyc.bank.gov.in",
            user_task="Submit KYC verification",
        )

        self.assertEqual(decision.action, PrivacyAction.TOKENIZE)
        self.assertEqual(decision.classified_entity, "AADHAAR")
        self.assertGreaterEqual(decision.confidence, 0.95)

    def test_public_support_email_kept_vs_user_email_tokenized(self):
        """Verify public support emails on website footer are kept while user emails are vaulted."""
        support_cand = PIIMatch(
            category=PIICategory.EMAIL,
            raw_value="support@service.com",
            placeholder="[EMAIL_1]",
            source_node_id=10,
        )
        footer_node = DOMNode(node_id=10, tag_name="a", element_type="link", text_content="support@service.com")
        support_dec = self.intelligence.evaluate_candidate(support_cand, node=footer_node, domain="https://service.com")
        self.assertEqual(support_dec.action, PrivacyAction.KEEP)
        self.assertEqual(support_dec.classified_entity, "PUBLIC_SUPPORT_EMAIL")

        # User personal email
        user_cand = PIIMatch(
            category=PIICategory.EMAIL,
            raw_value="john.doe.personal@gmail.com",
            placeholder="[EMAIL_2]",
            source_node_id=11,
        )
        input_node = DOMNode(node_id=11, tag_name="input", element_type="email", text_content="", value="john.doe.personal@gmail.com")
        user_dec = self.intelligence.evaluate_candidate(user_cand, node=input_node, domain="https://checkout.service.com")
        self.assertEqual(user_dec.action, PrivacyAction.TOKENIZE)
        self.assertEqual(user_dec.classified_entity, "PERSONAL_EMAIL")

    def test_credit_card_and_password_strictly_tokenized(self):
        """Verify password and credit cards are unconditionally tokenized."""
        pw_cand = PIIMatch(category=PIICategory.PASSWORD, raw_value="MyP@ss123", placeholder="[PASSWORD_1]")
        card_cand = PIIMatch(category=PIICategory.CREDIT_CARD, raw_value="4111222233334444", placeholder="[CARD_1]")

        self.assertEqual(self.intelligence.evaluate_candidate(pw_cand).action, PrivacyAction.TOKENIZE)
        self.assertEqual(self.intelligence.evaluate_candidate(card_cand).action, PrivacyAction.TOKENIZE)


if __name__ == "__main__":
    unittest.main()
