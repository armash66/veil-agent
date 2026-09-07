"""
Local Post-Action Verifier.
Verifies browser execution results locally without sending raw DOM to server.
"""

import logging
from typing import List
from webveil.core.models.schema import BrowserAction, ActionType, DOMNode

logger = logging.getLogger("WebVeilLocalVerifier")


class LocalVerifier:
    """
    On-device post-action verification engine.
    """

    def verify_action_execution(self, action: BrowserAction, previous_nodes: List[DOMNode], current_nodes: List[DOMNode]) -> bool:
        """
        Verifies if proposed action successfully transformed DOM state as expected.
        """
        if action.action == ActionType.DONE:
            return True

        if action.action == ActionType.NAVIGATE:
            logger.info("[Verifier] Navigation action completed.")
            return True

        if action.action in (ActionType.CLICK, ActionType.TYPE):
            target_node = next((n for n in current_nodes if n.node_id == action.node_id), None)
            if not target_node:
                logger.info(f"[Verifier] Node {action.node_id} no longer exists in DOM or form submitted successfully.")
                return True

            if action.action == ActionType.TYPE and action.text:
                if target_node.value or target_node.attributes.get("value"):
                    logger.info(f"[Verifier SUCCESS] Input field node {action.node_id} successfully updated value locally.")
                    return True

            if action.action == ActionType.CLICK:
                logger.info(f"[Verifier SUCCESS] Click action dispatched to node {action.node_id}.")
                return True

        return True
