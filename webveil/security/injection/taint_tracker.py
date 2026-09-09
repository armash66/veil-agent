"""
Taint Provenance Tracker.
Tracks untrusted page content and monitors whether proposed agent actions
have been poisoned by indirect prompt injections.
"""

import logging
from typing import Set, Dict, Tuple, Optional
from webveil.core.models.schema import BrowserAction, DOMNode
from webveil.security.injection.classifier import InjectionRiskAssessment

logger = logging.getLogger("WebVeilSecurity.TaintTracker")


class TaintTracker:
    """
    Maintains provenance data for tainted nodes and detects when proposed
    action parameters match malicious page instructions.
    """

    def __init__(self):
        self.tainted_node_ids: Set[int] = set()
        self.tainted_snippets: Dict[int, str] = {}
        self.tainted_urls: Set[str] = set()

    def clear(self):
        """Reset taint registry."""
        self.tainted_node_ids.clear()
        self.tainted_snippets.clear()
        self.tainted_urls.clear()

    def register_threats(self, threats: Dict[int, InjectionRiskAssessment]):
        """
        Record detected injection nodes and extract potential exfiltration URLs.
        """
        import re
        for node_id, assessment in threats.items():
            self.tainted_node_ids.add(node_id)
            snippet = assessment.matched_text_snippet
            if snippet:
                self.tainted_snippets[node_id] = snippet

            # Extract any embedded URLs from raw text and matched snippets
            search_corpus = f"{assessment.raw_text} {snippet}"
            urls = re.findall(r'https?://[^\s<>"]+', search_corpus)
            for u in urls:
                self.tainted_urls.add(u.lower().rstrip(".,;/"))

    def is_node_tainted(self, node_id: Optional[int]) -> bool:
        """Check if a specific node_id has been flagged as tainted."""
        return node_id in self.tainted_node_ids if node_id is not None else False

    def is_action_tainted(self, action: BrowserAction) -> Tuple[bool, str]:
        """
        Inspect proposed action for taint contamination:
        - Interacting with an injection-bearing node
        - Navigating to an untrusted URL embedded in an injection
        - Typing a payload originating from an untrusted source
        """
        # Check 1: Action targets a tainted node
        if action.node_id is not None and action.node_id in self.tainted_node_ids:
            snippet = self.tainted_snippets.get(action.node_id, "indirect injection")
            return True, f"Target node [{action.node_id}] is tainted by injection: '{snippet}'"

        # Check 2: Navigation to exfiltration endpoint
        if action.url:
            act_url_lower = action.url.lower()
            if any(tainted_u in act_url_lower for tainted_u in self.tainted_urls):
                return True, f"Action proposes navigation to tainted injection URL: {action.url}"

            if any(term in act_url_lower for term in ["leak", "exfil", "webhook.site", "hacker"]):
                return True, f"Action proposes navigation to suspicious exfiltration endpoint: {action.url}"

        # Check 3: Text contains exfiltration or command directives
        if action.text:
            txt_lower = action.text.lower()
            if any(tainted_u in txt_lower for tainted_u in self.tainted_urls):
                return True, f"Action text contains tainted exfiltration URL."

        return False, ""
