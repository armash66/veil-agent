"""
Action Firewall & Placeholder Interceptor.
Validates proposed actions, checks node freshness, and manages local secret restoration.
"""

import logging
from typing import Dict, Optional, List
from webveil.core.models.schema import BrowserAction, ActionType, DOMNode
from webveil.core.vault.client_vault import ClientVault, VaultRestorationError
from webveil.browser.base_adapter import BaseBrowserAdapter

logger = logging.getLogger("WebVeilActionFirewall")


class ActionSecurityViolation(Exception):
    """Raised when an unauthorized or dangerous action is proposed by the server."""
    pass


class ActionFirewall:
    """
    Firewall inspecting server action proposals, validating node freshness, and resolving vault placeholders locally.
    """

    ALLOWED_ACTIONS = {ActionType.NAVIGATE, ActionType.CLICK, ActionType.TYPE, ActionType.SCROLL, ActionType.KEYPRESS, ActionType.SELECT, ActionType.WAIT, ActionType.DONE}

    def __init__(self, vault: ClientVault, browser: BaseBrowserAdapter):
        self.vault = vault
        self.browser = browser

    def validate_action_schema(self, action: BrowserAction):
        """
        Validates action against allowed white-list schema.
        """
        if action.action not in self.ALLOWED_ACTIONS:
            logger.critical(f"[FIREWALL REJECT] Unauthorized action attempted: '{action.action}'")
            raise ActionSecurityViolation(f"Action '{action.action}' is blocked by WebVeil Action Firewall")

        if action.action == ActionType.TYPE:
            if action.node_id is None or action.text is None:
                raise ActionSecurityViolation("Action 'type' requires valid node_id and text")

        if action.action == ActionType.CLICK and action.node_id is None:
            raise ActionSecurityViolation("Action 'click' requires valid node_id")

        if action.action == ActionType.NAVIGATE and not action.url:
            raise ActionSecurityViolation("Action 'navigate' requires valid url")

    def execute_validated_action(self, action: BrowserAction, current_dom_nodes: List[DOMNode], current_origin: str) -> bool:
        """
        Validates action, checks node freshness, resolves vault secrets if needed, and dispatches to browser.
        """
        # 1. Schema Validation
        self.validate_action_schema(action)

        if action.action == ActionType.DONE:
            logger.info("[Agent Step] Task complete signaled by server.")
            return True

        if action.action == ActionType.WAIT:
            logger.info("[Agent Step] Waiting for page state stabilization.")
            return True

        if action.action == ActionType.NAVIGATE:
            logger.info(f"[Agent Step] Navigating to {action.url}")
            self.browser.navigate(action.url)
            return True

        if action.action == ActionType.SCROLL:
            logger.info(f"[Agent Step] Scrolling {action.direction} by {action.amount}")
            return self.browser.scroll_page(action.direction or "down", action.amount or 300)

        if action.action == ActionType.KEYPRESS:
            logger.info(f"[Agent Step] Pressing key {action.key}")
            return self.browser.press_key(action.key or "Enter")

        # 2. Node Freshness & Identity Check
        target_node = next((n for n in current_dom_nodes if n.node_id == action.node_id), None)
        if not target_node:
            logger.error(f"[FIREWALL REJECT] Node {action.node_id} is stale or no longer attached to DOM")
            raise ActionSecurityViolation(f"Node {action.node_id} not found in active DOM observation")

        # 3. Action Type Handling: CLICK
        if action.action == ActionType.CLICK:
            logger.info(f"[Agent Step] Clicking node [{target_node.node_id}] <{target_node.tag_name}>")
            return self.browser.click_element(target_node.node_id)

        # 4. Action Type Handling: TYPE & Vault Interception
        if action.action == ActionType.TYPE:
            text_to_type = action.text
            
            # Check if text is a vault placeholder token (e.g. "[PASSWORD_1]")
            if text_to_type.startswith("[") and text_to_type.endswith("]"):
                logger.info(f"[Firewall Interceptor] Token detected '{text_to_type}'. Restoring secret locally...")
                text_to_type = self.vault.restore(text_to_type, target_node, current_origin)
                action.placeholder_restored = True

            logger.info(f"[Agent Step] Typing into node [{target_node.node_id}] (Secret restored locally)")
            return self.browser.type_text(target_node.node_id, text_to_type)

        # 5. Action Type Handling: SELECT
        if action.action == ActionType.SELECT:
            logger.info(f"[Agent Step] Selecting option '{action.value}' in node [{target_node.node_id}]")
            return self.browser.select_option(target_node.node_id, action.value or "")

        return False
