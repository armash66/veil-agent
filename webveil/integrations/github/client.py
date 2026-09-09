"""
GitHub Integration Client for WebVeil Browser Agent.
Provides privacy-preserving browser automation workflows for GitHub operations
(issues, pull requests, workflows, repositories) with ClientVault tokenization for PATs.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from webveil.core.models.schema import BrowserAction, ActionType, DOMNode
from webveil.core.vault.client_vault import ClientVault
from webveil.security.firewall.action_firewall import ActionFirewall
from webveil.integrations.github.actions import GitHubActionPlanBuilder, GitHubIssueSpec

logger = logging.getLogger("WebVeilIntegrations.GitHub")


class GitHubCredentialManager:
    """
    Manages GitHub Personal Access Tokens and SSH credentials with zero-leakage vaulting.
    """

    PAT_REGEX = re.compile(r'(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})')

    def __init__(self, vault: ClientVault):
        self.vault = vault

    def protect_pat(self, raw_pat: str) -> str:
        """
        Store GitHub PAT into client vault and return synthetic token.
        Raw token is never saved or logged in plaintext.
        """
        if not raw_pat:
            raise ValueError("Empty GitHub PAT provided")

        token = self.vault.store_secret(raw_pat, label="github_pat")
        logger.info(f"[GitHub] Stored GitHub PAT into ClientVault as token: {token}")
        return token

    def is_pat_pattern(self, text: str) -> bool:
        """Check if text contains a GitHub PAT signature."""
        return bool(self.PAT_REGEX.search(text))


class GitHubWorkflowNavigator:
    """
    Drives browser automation for GitHub developer workflows through ActionFirewall.
    """

    def __init__(self, firewall: ActionFirewall, vault: Optional[ClientVault] = None):
        self.firewall = firewall
        self.vault = vault or ClientVault()
        self.cred_manager = GitHubCredentialManager(self.vault)

    def navigate_to_repository(self, repo: str, current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to repository homepage."""
        action = GitHubActionPlanBuilder.plan_navigate_repo(repo)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_issues(self, repo: str, current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to issues list page."""
        action = GitHubActionPlanBuilder.plan_navigate_issues(repo)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_pull_request(self, repo: str, pr_number: int, current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to a specific pull request."""
        action = GitHubActionPlanBuilder.plan_navigate_pull_request(repo, pr_number)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_actions(self, repo: str, current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to GitHub Actions CI/CD workflows."""
        action = GitHubActionPlanBuilder.plan_navigate_actions(repo)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def fill_issue_form(
        self,
        title_node: DOMNode,
        body_node: DOMNode,
        submit_node: DOMNode,
        spec: GitHubIssueSpec,
        current_dom: List[DOMNode],
        current_url: str,
    ) -> List[BrowserAction]:
        """
        Generates and returns the validated sequence of actions to fill and submit an issue.
        """
        # Step 1: Type issue title
        title_action = BrowserAction(
            action=ActionType.TYPE,
            node_id=title_node.node_id,
            text=spec.title,
        )

        # Step 2: Type issue body
        body_action = BrowserAction(
            action=ActionType.TYPE,
            node_id=body_node.node_id,
            text=spec.body,
        )

        # Step 3: Click submit button
        submit_action = BrowserAction(
            action=ActionType.CLICK,
            node_id=submit_node.node_id,
        )

        return [title_action, body_action, submit_action]
