"""
Prompt Injection Firewall Rule.
Enforces security boundary checks to block poisoned or tainted browser actions.
"""

import logging
from typing import List, Optional
from webveil.core.models.schema import BrowserAction, DOMNode, SanitizedWorldModel
from webveil.security.injection.classifier import PromptInjectionClassifier
from webveil.security.injection.taint_tracker import TaintTracker

logger = logging.getLogger("WebVeilSecurity.InjectionFirewall")


class PromptInjectionViolation(Exception):
    """Raised when an action is blocked due to prompt injection taint."""
    pass


class PromptInjectionFirewallRule:
    """
    Firewall enforcement rule blocking execution of poisoned or tainted browser actions.
    """

    def __init__(self):
        self.classifier = PromptInjectionClassifier()
        self.taint_tracker = TaintTracker()

    def update_taint_from_nodes(self, nodes: List[DOMNode]):
        """Scan active DOM nodes and register any detected prompt injection threats."""
        threats = {}
        for node in nodes:
            assessment = self.classifier.scan_dom_node(node)
            if assessment.is_injection:
                threats[node.node_id] = assessment
        self.taint_tracker.register_threats(threats)

    def validate_proposed_action(self, action: BrowserAction):
        """
        Evaluate proposed action against taint tracker.
        Raises PromptInjectionViolation if tainted.
        """
        is_tainted, reason = self.taint_tracker.is_action_tainted(action)
        if is_tainted:
            logger.critical(f"[FIREWALL INJECTION BLOCK] {reason}")
            raise PromptInjectionViolation(f"Action blocked by Prompt Injection Defense: {reason}")
