"""
Unit tests for WebVeil AWS Remote Browser Adapter and Console Navigation.
Tests remote adapter lifecycle, CDP dispatching, credential protection, and console action routes.
"""

import unittest
from unittest.mock import MagicMock

from webveil.browser.aws_adapter import AWSRemoteBrowserConfig, AWSCredentialManager, AWSRemoteBrowserAdapter
from webveil.core.models.schema import DOMNode, ActionType
from webveil.core.vault.client_vault import ClientVault
from webveil.integrations.aws.actions import AWSActionPlanBuilder
from webveil.security.firewall.action_firewall import ActionFirewall


class TestAWSRemoteBrowser(unittest.TestCase):

    def setUp(self):
        self.vault = ClientVault()
        self.config = AWSRemoteBrowserConfig(
            endpoint_url="wss://cdp.eu-north-1.amazonaws.com/session-1234",
            region="eu-north-1",
        )
        self.adapter = AWSRemoteBrowserAdapter(self.config, vault=self.vault)
        self.mock_cdp = MagicMock()
        self.adapter.set_cdp_client(self.mock_cdp)

    def test_aws_credential_manager_vaulting(self):
        """Verify AWS Access Key and Secret Key are tokenized without leaks."""
        cred_mgr = AWSCredentialManager(self.vault)

        access_key = "AKIAIOSFODNN7EXAMPLE"
        self.assertTrue(cred_mgr.is_access_key(access_key))

        token_ak = cred_mgr.protect_access_key(access_key)
        self.assertIn("{{VAULT_TOKEN_AWS_ACCESS_KEY_", token_ak)
        self.assertNotIn(access_key, token_ak)
        self.assertEqual(self.vault.get_secret_unverified(token_ak), access_key)

        secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        token_sk = cred_mgr.protect_secret_key(secret_key)
        self.assertIn("{{VAULT_TOKEN_AWS_SECRET_KEY_", token_sk)
        self.assertNotIn(secret_key, token_sk)
        self.assertEqual(self.vault.get_secret_unverified(token_sk), secret_key)

    def test_remote_browser_lifecycle_and_dispatch(self):
        """Verify connect, navigate, click, type, and stop commands."""
        # Must fail when not started
        with self.assertRaises(RuntimeError):
            self.adapter.navigate("https://example.com")

        # Start session
        self.adapter.start()
        self.assertTrue(self.adapter.is_connected)
        self.mock_cdp.connect.assert_called_with(self.config.endpoint_url)

        # Navigate
        self.adapter.navigate("https://eu-north-1.console.aws.amazon.com")
        self.assertEqual(self.adapter.get_current_url(), "https://eu-north-1.console.aws.amazon.com")
        self.mock_cdp.navigate.assert_called_with("https://eu-north-1.console.aws.amazon.com")

        # Interactions
        self.adapter.click_element(42)
        self.mock_cdp.click_element.assert_called_with(42)

        self.adapter.type_text(42, "hello")
        self.mock_cdp.type_text.assert_called_with(42, "hello")

        self.adapter.press_key("Enter")
        self.mock_cdp.press_key.assert_called_with("Enter")

        self.adapter.scroll_page("down", 500)
        self.mock_cdp.scroll_page.assert_called_with("down", 500)

        # Stop
        self.adapter.stop()
        self.assertFalse(self.adapter.is_connected)
        self.mock_cdp.close.assert_called_once()

    def test_aws_action_plan_builder_urls(self):
        """Verify AWS Console URL routing."""
        console = AWSActionPlanBuilder.plan_navigate_console("eu-north-1")
        self.assertIn("eu-north-1.console.aws.amazon.com", console.url)

        ec2 = AWSActionPlanBuilder.plan_navigate_ec2("eu-north-1")
        self.assertIn("ec2/home?region=eu-north-1", ec2.url)

        s3 = AWSActionPlanBuilder.plan_navigate_s3()
        self.assertIn("s3/buckets", s3.url)

        lam = AWSActionPlanBuilder.plan_navigate_lambda("us-east-1")
        self.assertIn("us-east-1.console.aws.amazon.com/lambda", lam.url)

        iam = AWSActionPlanBuilder.plan_navigate_iam()
        self.assertIn("iam/home#/users", iam.url)

    def test_firewall_integration_with_aws_adapter(self):
        """Verify ActionFirewall can drive the remote AWS adapter."""
        self.adapter.start()
        firewall = ActionFirewall(vault=self.vault, browser=self.adapter)

        nodes = [DOMNode(node_id=1, tag_name="button", text_content="Launch Instance", is_visible=True, is_interactive=True)]
        action = AWSActionPlanBuilder.plan_navigate_ec2("eu-north-1")
        success = firewall.execute_validated_action(action, nodes, "about:blank")
        self.assertTrue(success)
        self.assertEqual(self.adapter.get_current_url(), action.url)


if __name__ == "__main__":
    unittest.main()
