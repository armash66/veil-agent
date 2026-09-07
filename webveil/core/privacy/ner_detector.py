"""
Local PII NER & Risk Fusion Engine.
Combines deterministic regex/metadata detection with local NER pattern analysis.
Enforces conservative security precedence (Deterministic Regex = 1.0 overrides lower-confidence NER).
"""

import re
import logging
from typing import List, Tuple, Dict, Any, Optional
from webveil.core.models.schema import DOMNode, PIIMatch, PIICategory, PrivacyDecision
from webveil.core.privacy.pii_detector import LocalPIIDetector

logger = logging.getLogger("WebVeilPIINer")


class LocalPIINerEngine:
    """
    Hybrid PII detection & risk fusion engine.
    Precedence: Deterministic Regex/Password > Metadata > Semantic NER.
    """

    def __init__(self, detector: LocalPIIDetector):
        self.detector = detector
        # Lightweight NER regex patterns for names, addresses, and secret tokens
        self.NAME_PATTERN = re.compile(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b')
        self.ADDRESS_PATTERN = re.compile(r'\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Nagar|Colony|Sector)\b', re.IGNORECASE)

    def detect_and_fuse(self, node: DOMNode, origin: str) -> List[PrivacyDecision]:
        decisions: List[PrivacyDecision] = []

        # 1. Primary Scan via LocalPIIDetector (Deterministic Regex & Metadata)
        deterministic_matches = self.detector.scan_dom_node(node)
        for m in deterministic_matches:
            decisions.append(PrivacyDecision(
                entity_type=m.category.name,
                raw_value=m.raw_value,
                placeholder=m.placeholder,
                confidence=1.0,  # Deterministic precedence
                sources=["regex" if "Pattern" in m.context else "metadata"],
                action="REDACT",
                source_node_id=node.node_id
            ))

        # 2. Supplementary Local NER Scan (Unstructured Text)
        text_to_scan = f"{node.text_content} {node.value}".strip()
        if text_to_scan and not any(d.confidence == 1.0 for d in decisions):
            # Scan for Person Names
            for nm in self.NAME_PATTERN.finditer(text_to_scan):
                raw = nm.group(0)
                if not any(d.raw_value == raw for d in decisions):
                    ph = f"[NAME_{len(decisions)+1}]"
                    decisions.append(PrivacyDecision(
                        entity_type="NAME",
                        raw_value=raw,
                        placeholder=ph,
                        confidence=0.88,
                        sources=["ner"],
                        action="REDACT",
                        source_node_id=node.node_id
                    ))

            # Scan for Addresses
            for add in self.ADDRESS_PATTERN.finditer(text_to_scan):
                raw = add.group(0)
                if not any(d.raw_value == raw for d in decisions):
                    ph = f"[ADDRESS_{len(decisions)+1}]"
                    decisions.append(PrivacyDecision(
                        entity_type="ADDRESS",
                        raw_value=raw,
                        placeholder=ph,
                        confidence=0.85,
                        sources=["ner"],
                        action="REDACT",
                        source_node_id=node.node_id
                    ))

        return decisions
