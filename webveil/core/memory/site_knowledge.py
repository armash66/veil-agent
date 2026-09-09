"""
Semantic Site Knowledge Store.
Learns and caches site structural invariants (search bar selectors, login paths, pagination structures)
across user sessions to accelerate repeated browser tasks with zero PII retention.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from webveil.core.memory.guard import ZeroPIIMemoryGuard

logger = logging.getLogger("WebVeilMemory.SiteKnowledge")


@dataclass
class SitePattern:
    domain: str
    action_type: str  # e.g. "search", "login", "checkout", "pagination"
    selector_hints: List[str] = field(default_factory=list)
    common_path: str = ""
    notes: str = ""


class SiteKnowledgeStore:
    """
    Registry of domain navigation and interaction patterns.
    """

    # Pre-seeded common platform patterns for rapid zero-shot bootstrapping
    DEFAULT_PATTERNS = [
        SitePattern(domain="github.com", action_type="search", selector_hints=["input[name='q']", "button[data-target='qbsearch-input.inputButton']"], common_path="/search"),
        SitePattern(domain="amazon.in", action_type="search", selector_hints=["input#twotabsearchtextbox", "input[name='field-keywords']"], common_path="/s"),
        SitePattern(domain="amazon.com", action_type="search", selector_hints=["input#twotabsearchtextbox", "input[name='field-keywords']"], common_path="/s"),
        SitePattern(domain="wikipedia.org", action_type="search", selector_hints=["input#searchInput", "input[name='search']"], common_path="/w/index.php"),
        SitePattern(domain="console.aws.amazon.com", action_type="nav", selector_hints=["button[data-testid='awsc-nav-services-menu']"], common_path="/console/home"),
        SitePattern(domain="vercel.com", action_type="nav", selector_hints=["button[data-testid='project-search']"], common_path="/dashboard"),
    ]

    def __init__(self, guard: Optional[ZeroPIIMemoryGuard] = None):
        self.guard = guard or ZeroPIIMemoryGuard()
        self._patterns: Dict[str, Dict[str, SitePattern]] = {}

        # Seed defaults
        for p in self.DEFAULT_PATTERNS:
            self.learn_pattern(p)

    def learn_pattern(self, pattern: SitePattern):
        """Register or update a site pattern after privacy check."""
        self.guard.assert_clean(pattern.notes, context="pattern_notes")
        for hint in pattern.selector_hints:
            self.guard.assert_clean(hint, context="selector_hint")

        dom_key = pattern.domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        if dom_key not in self._patterns:
            self._patterns[dom_key] = {}

        self._patterns[dom_key][pattern.action_type.lower()] = pattern
        logger.info(f"[SiteKnowledge] Stored pattern for '{dom_key}' ({pattern.action_type})")

    def lookup_pattern(self, domain: str, action_type: str) -> Optional[SitePattern]:
        """Query pattern for a domain and action type, supporting subdomain fallback."""
        dom_key = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]

        # 1. Exact domain match
        site_entry = self._patterns.get(dom_key)
        if site_entry and action_type.lower() in site_entry:
            return site_entry[action_type.lower()]

        # 2. Suffix / parent domain match (e.g. "en.wikipedia.org" -> "wikipedia.org")
        for stored_dom, entries in self._patterns.items():
            if dom_key.endswith(f".{stored_dom}") or dom_key == stored_dom:
                if action_type.lower() in entries:
                    return entries[action_type.lower()]

        return None

    def list_known_domains(self) -> List[str]:
        return sorted(list(self._patterns.keys()))
