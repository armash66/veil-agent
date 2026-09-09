"""
Unit tests for WebVeil GitHub Integration.
Tests credential tokenization, action plan building, and workflow navigation.
"""

import unittest
from unittest.mock import MagicMock

from webveil.core.models.schema import DOMNode, ActionType
from webveil.core.vault.client_vault import ClientVault
from webveil.security.firewall.action_firewall import ActionFirewall
from webveil.integrations.github.actions import GitHubActionPlanBuilder, GitHubIssueSpec
from webveil.integrations.github.client import GitHubCredentialManager, GitHubWorkflowNavigator


class TestGitHubIntegration(unittest.TestCase):

    def setUp(self):
        self.vault = ClientVault()
        self.mock_browser = MagicMock()
        self.mock_browser.navigate.return_value = True
        self.mock_browser.click_element.return_value = True
        self.mock_browser.type_text.return_value = True

        self.firewall = ActionFirewall(vault=self.vault, browser=self.mock_browser)
        self.navigator = GitHubWorkflowNavigator(firewall=self.firewall, vault=self.vault)
        self.cred_manager = GitHubCredentialManager(self.vault)

    def test_github_action_plan_builder_urls(self):
        """Verify navigation action construction for GitHub paths."""
        repo_action = GitHubActionPlanBuilder.plan_navigate_repo("octocat/Hello-World")
        self.assertEqual(repo_action.action, ActionType.NAVIGATE)
        self.assertEqual(repo_action.url, "https://github.com/octocat/Hello-World")

        issues_action = GitHubActionPlanBuilder.plan_navigate_issues("octocat/Hello-World")
        self.assertEqual(issues_action.url, "https://github.com/octocat/Hello-World/issues")

        pr_action = GitHubActionPlanBuilder.plan_navigate_pull_request("octocat/Hello-World", 42)
        self.assertEqual(pr_action.url, "https://github.com/octocat/Hello-World/pull/42")

        actions_action = GitHubActionPlanBuilder.plan_navigate_actions("octocat/Hello-World")
        self.assertEqual(actions_action.url, "https://github.com/octocat/Hello-World/actions")

    def test_github_pat_credential_vaulting(self):
        """Verify GitHub PATs are tokenized and shielded in client memory."""
        classic_pat = "ghp_123456789012345678901234567890123456"
        self.assertTrue(self.cred_manager.is_pat_pattern(classic_pat))

        token = self.cred_manager.protect_pat(classic_pat)
        self.assertIn("{{VAULT_TOKEN_GITHUB_PAT_", token)
        self.assertNotIn(classic_pat, token)

        # Confirm retrieval from client vault
        self.assertEqual(self.vault.get_secret_unverified(token), classic_pat)

    def test_workflow_navigation_through_firewall(self):
        """Verify navigation dispatches cleanly via firewall."""
        current_dom = [DOMNode(node_id=1, tag_name="div", is_visible=True)]
        success = self.navigator.navigate_to_repository("org/project", current_dom, "https://github.com")
        self.assertTrue(success)
        self.mock_browser.navigate.assert_called_with("https://github.com/org/project")

    def test_fill_issue_form_actions(self):
        """Verify generation of multi-step issue creation actions."""
        title_node = DOMNode(node_id=10, tag_name="input", element_id="issue_title", is_visible=True, is_interactive=True)
        body_node = DOMNode(node_id=11, tag_name="textarea", element_id="issue_body", is_visible=True, is_interactive=True)
        submit_node = DOMNode(node_id=12, tag_name="button", text_content="Submit new issue", is_visible=True, is_interactive=True)

        spec = GitHubIssueSpec(repo="org/project", title="Bug: Memory leak in worker", body="Detailed bug report description.")
        actions = self.navigator.fill_issue_form(
            title_node, body_node, submit_node, spec, [title_node, body_node, submit_node], "https://github.com/org/project/issues/new"
        )

        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].action, ActionType.TYPE)
        self.assertEqual(actions[0].node_id, 10)
        self.assertEqual(actions[0].text, spec.title)

        self.assertEqual(actions[1].action, ActionType.TYPE)
        self.assertEqual(actions[1].node_id, 11)
        self.assertEqual(actions[1].text, spec.body)

        self.assertEqual(actions[2].action, ActionType.CLICK)
        self.assertEqual(actions[2].node_id, 12)


if __name__ == "__main__":
    unittest.main()
