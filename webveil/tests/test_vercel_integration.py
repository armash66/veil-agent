"""
Unit tests for WebVeil Vercel Integration.
Tests credential tokenization, environment variable vaulting, action planning, and navigation.
"""

import unittest
from unittest.mock import MagicMock

from webveil.core.models.schema import DOMNode, ActionType
from webveil.core.vault.client_vault import ClientVault
from webveil.security.firewall.action_firewall import ActionFirewall
from webveil.integrations.vercel.actions import VercelActionPlanBuilder, VercelEnvVarSpec
from webveil.integrations.vercel.client import VercelCredentialManager, VercelWorkflowNavigator


class TestVercelIntegration(unittest.TestCase):

    def setUp(self):
        self.vault = ClientVault()
        self.mock_browser = MagicMock()
        self.mock_browser.navigate.return_value = True
        self.mock_browser.click_element.return_value = True
        self.mock_browser.type_text.return_value = True

        self.firewall = ActionFirewall(vault=self.vault, browser=self.mock_browser)
        self.navigator = VercelWorkflowNavigator(firewall=self.firewall, vault=self.vault)
        self.cred_manager = VercelCredentialManager(self.vault)

    def test_vercel_action_plan_builder_urls(self):
        """Verify URL paths for Vercel actions."""
        dash = VercelActionPlanBuilder.plan_navigate_dashboard()
        self.assertEqual(dash.url, "https://vercel.com/dashboard")

        proj = VercelActionPlanBuilder.plan_navigate_project("my-app", "acme-team")
        self.assertEqual(proj.url, "https://vercel.com/acme-team/my-app")

        deployments = VercelActionPlanBuilder.plan_navigate_deployments("my-app", "acme-team")
        self.assertEqual(deployments.url, "https://vercel.com/acme-team/my-app/deployments")

        env_vars = VercelActionPlanBuilder.plan_navigate_env_vars("my-app", "acme-team")
        self.assertEqual(env_vars.url, "https://vercel.com/acme-team/my-app/settings/environment-variables")

    def test_vercel_token_and_env_var_vaulting(self):
        """Verify Vercel tokens and secret environment variable values are securely vaulted."""
        token_str = "vercel_1234567890abcdef12345678"
        self.assertTrue(self.cred_manager.is_token_pattern(token_str))

        token_placeholder = self.cred_manager.protect_token(token_str)
        self.assertIn("{{VAULT_TOKEN_VERCEL_TOKEN_", token_placeholder)
        self.assertNotIn(token_str, token_placeholder)
        self.assertEqual(self.vault.get_secret_unverified(token_placeholder), token_str)

        # Env var vaulting
        secret_db_url = "postgres://admin:supersecretpassword@db.prod.internal:5432/main"
        env_placeholder = self.cred_manager.protect_env_var_value("DATABASE_URL", secret_db_url)
        self.assertIn("{{VAULT_TOKEN_VERCEL_ENV_DATABASE_URL_", env_placeholder)
        self.assertNotIn(secret_db_url, env_placeholder)
        self.assertEqual(self.vault.get_secret_unverified(env_placeholder), secret_db_url)

    def test_fill_env_var_form_masks_secrets(self):
        """Verify fill_env_var_form produces actions where text contains only vault tokens, never raw secrets."""
        key_node = DOMNode(node_id=1, tag_name="input", element_id="env_key", is_visible=True, is_interactive=True)
        val_node = DOMNode(node_id=2, tag_name="input", element_id="env_val", is_visible=True, is_interactive=True)
        save_node = DOMNode(node_id=3, tag_name="button", text_content="Save", is_visible=True, is_interactive=True)

        raw_secret_api_key = "sk_live_verysecretstripekey987654321"
        spec = VercelEnvVarSpec(key="STRIPE_SECRET_KEY", value=raw_secret_api_key, target_environments=["production"])

        actions = self.navigator.fill_env_var_form(
            key_node, val_node, save_node, spec, [key_node, val_node, save_node], "https://vercel.com/team/app/settings/environment-variables"
        )

        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].text, "STRIPE_SECRET_KEY")
        # Action payload MUST NOT contain the raw secret!
        self.assertNotIn(raw_secret_api_key, actions[1].text)
        self.assertIn("{{VAULT_TOKEN_", actions[1].text)


if __name__ == "__main__":
    unittest.main()
