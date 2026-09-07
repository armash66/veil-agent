"""
Simulated Server VLM / Reasoning Engine.
Receives ONLY sanitized DOM + redacted screenshots and returns constrained JSON action proposals.
"""

import logging
from typing import Dict, Any, List
from webveil.core.models.schema import BrowserAction, ActionType

logger = logging.getLogger("WebVeilVLMServer")


class VLMServerReasoningEngine:
    """
    Server-side reasoning engine simulation.
    Operates strictly on sanitized DOM and placeholder tokens.
    """

    def process_sanitized_request(self, payload: Dict[str, Any]) -> BrowserAction:
        """
        Receives authorized sanitized payload from EgressPrivacyGate.
        Inspects sanitized DOM and generates next action proposal.
        """
        task = payload.get("task", "").lower()
        dom = payload.get("dom", "")
        action_history = payload.get("action_history", [])

        logger.info(f"[Server VLM] Processing sanitized context for task: '{task}'")
        logger.info(f"[Server VLM] Received sanitized DOM string length: {len(dom)} chars")

        lines = dom.split("\n")
        interactive_nodes: List[Dict[str, Any]] = []

        for line in lines:
            if not line.strip() or not line.startswith("["):
                continue
            try:
                node_id = int(line.split("]")[0].replace("[", ""))
                rest = line.split("]", 1)[1].strip()
                interactive_nodes.append({"node_id": node_id, "raw_line": rest.lower()})
            except Exception:
                continue

        typed_node_ids = set(a.get("node_id") for a in action_history if a.get("action") == "type")
        clicked_node_ids = set(a.get("node_id") for a in action_history if a.get("action") == "click")

        # Step-by-step form completion
        for item in interactive_nodes:
            nid = item["node_id"]
            line = item["raw_line"]

            if "name" in line and "input" in line and nid not in typed_node_ids:
                return BrowserAction(action=ActionType.TYPE, node_id=nid, text="Armash Test User")

            if ("email" in line or "[email_" in line) and "input" in line and nid not in typed_node_ids:
                return BrowserAction(action=ActionType.TYPE, node_id=nid, text="[EMAIL_1]")

            if ("phone" in line or "[phone_" in line) and "input" in line and nid not in typed_node_ids:
                return BrowserAction(action=ActionType.TYPE, node_id=nid, text="[PHONE_1]")

            if ("aadhaar" in line or "[aadhaar_" in line) and "input" in line and nid not in typed_node_ids:
                return BrowserAction(action=ActionType.TYPE, node_id=nid, text="[AADHAAR_1]")

            if ("password" in line or "[password_" in line) and "input" in line and nid not in typed_node_ids:
                return BrowserAction(action=ActionType.TYPE, node_id=nid, text="[PASSWORD_1]")

            if ("submit" in line or "button" in line) and nid not in clicked_node_ids:
                return BrowserAction(action=ActionType.CLICK, node_id=nid)

        return BrowserAction(action=ActionType.DONE)
