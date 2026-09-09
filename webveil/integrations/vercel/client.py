"""
Vercel Integration Client for WebVeil Browser Agent.
Provides privacy-preserving browser automation workflows for Vercel operations
(deployments, environment variables, settings) with ClientVault tokenization for tokens & secrets.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from webveil.core.models.schema import BrowserAction, ActionType, DOMNode
from webveil.core.vault.client_vault import ClientVault
from webveil.security.firewall.action_firewall import ActionFirewall
from webveil.integrations.vercel.actions import VercelActionPlanBuilder, VercelEnvVarSpec

logger = logging.getLogger("WebVeilIntegrations.Vercel")


class VercelCredentialManager:
    """
    Protects Vercel API tokens and sensitive deployment environment variable values.
    """

    TOKEN_REGEX = re.compile(r'vercel_[a-zA-Z0-9_-]{24,}')

    def __init__(self, vault: ClientVault):
        self.vault = vault

    def protect_token(self, raw_token: str) -> str:
        """Store Vercel token into client vault and return synthetic token."""
        if not raw_token:
            raise ValueError("Empty Vercel token provided")

        token = self.vault.store_secret(raw_token, label="vercel_token")
        logger.info(f"[Vercel] Stored Vercel token into ClientVault: {token}")
        return token

    def protect_env_var_value(self, var_name: str, raw_val: str) -> str:
        """Store sensitive environment variable value into client vault."""
        if not raw_val:
            return ""

        token = self.vault.store_secret(raw_val, label=f"vercel_env_{var_name.lower()}")
        logger.info(f"[Vercel] Vaulted env secret for '{var_name}' as {token}")
        return token

    def is_token_pattern(self, text: str) -> bool:
        """Check if text contains a Vercel bearer token signature."""
        return bool(self.TOKEN_REGEX.search(text))


class VercelWorkflowNavigator:
    """
    Drives browser automation for Vercel workflows through ActionFirewall.
    """

    def __init__(self, firewall: ActionFirewall, vault: Optional[ClientVault] = None):
        self.firewall = firewall
        self.vault = vault or ClientVault()
        self.cred_manager = VercelCredentialManager(self.vault)

    def navigate_to_dashboard(self, current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to Vercel dashboard."""
        action = VercelActionPlanBuilder.plan_navigate_dashboard()
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_project(self, project: str, team: Optional[str], current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to project overview."""
        action = VercelActionPlanBuilder.plan_navigate_project(project, team)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_deployments(self, project: str, team: Optional[str], current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to project deployments list."""
        action = VercelActionPlanBuilder.plan_navigate_deployments(project, team)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def navigate_to_env_vars(self, project: str, team: Optional[str], current_dom: List[DOMNode], current_url: str = "about:blank") -> bool:
        """Navigate to project environment variables settings."""
        action = VercelActionPlanBuilder.plan_navigate_env_vars(project, team)
        return self.firewall.execute_validated_action(action, current_dom, current_url)

    def fill_env_var_form(
        self,
        key_node: DOMNode,
        val_node: DOMNode,
        save_node: DOMNode,
        spec: VercelEnvVarSpec,
        current_dom: List[DOMNode],
        current_url: str,
    ) -> List[BrowserAction]:
        """
        Vaults the secret environment value and returns validated browser action sequence.
        """
        # Store secret in vault to produce token
        safe_token = self.cred_manager.protect_env_var_value(spec.key, spec.value)

        key_action = BrowserAction(
            action=ActionType.TYPE,
            node_id=key_node.node_id,
            text=spec.key,
        )

        val_action = BrowserAction(
            action=ActionType.TYPE,
            node_id=val_node.node_id,
            text=safe_token,
        )

        save_action = BrowserAction(
            action=ActionType.CLICK,
            node_id=save_node.node_id,
        )

        return [key_action, val_action, save_action]
