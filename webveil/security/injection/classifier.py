"""
Indirect Prompt Injection Classifier.
Inspects DOM text, attributes, comments, and visual OCR text
to detect prompt hijacking, system overrides, and data exfiltration vectors.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import DOMNode, SanitizedWorldModel

logger = logging.getLogger("WebVeilSecurity.Injection")


@dataclass
class InjectionRiskAssessment:
    risk_score: float
    is_injection: bool
    detected_signatures: List[str] = field(default_factory=list)
    matched_text_snippet: str = ""
    raw_text: str = ""
    source_node_id: Optional[int] = None


class PromptInjectionClassifier:
    """
    Scans web content for adversarial indirect prompt injection attempts.
    """

    # Adversarial pattern signatures
    INJECTION_PATTERNS = [
        ("INSTRUCTION_OVERRIDE", re.compile(r'ignore (?:all )?(?:previous|prior|above) (?:instructions|prompts|rules|commands)', re.IGNORECASE)),
        ("SYSTEM_PROMPT_OVERRIDE", re.compile(r'system (?:prompt )?override|new system directive', re.IGNORECASE)),
        ("JAILBREAK_MODE", re.compile(r'you are now (?:in )?(?:a )?(?:developer|dan|jailbreak|unrestricted|sudo) mode', re.IGNORECASE)),
        ("DISREGARD_PRIOR", re.compile(r'(?:disregard|forget) (?:all |everything )(?:prior|previous|above)', re.IGNORECASE)),
        ("AI_TARGETED_DIRECTIVE", re.compile(r'(?:note to |attention |dear )?(?:ai agent|ai assistant|llm|webveil)\s*:', re.IGNORECASE)),
        ("SECRET_EXFILTRATION", re.compile(r'(?:post|send|transmit|exfiltrate|leak) (?:the )?(?:vault|secrets?|tokens?|passwords?|aadhaar|credentials?)', re.IGNORECASE)),
        ("SUSPICIOUS_EXFIL_URL", re.compile(r'(?:https?://[^\s]+(?:leak|steal|exfil|hacker|malicious|evil|webhook))', re.IGNORECASE)),
        ("JAVASCRIPT_URI", re.compile(r'javascript:\s*[^\s]+', re.IGNORECASE)),
    ]

    def scan_text(self, text: str, node_id: Optional[int] = None) -> InjectionRiskAssessment:
        """
        Scan a single text string for prompt injection signatures.
        """
        if not text:
            return InjectionRiskAssessment(risk_score=0.0, is_injection=False, source_node_id=node_id)

        detected_signatures: List[str] = []
        snippets: List[str] = []
        score = 0.0

        for sig_name, pattern in self.INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                detected_signatures.append(sig_name)
                snippets.append(match.group(0))
                # High severity signatures
                if sig_name in ["INSTRUCTION_OVERRIDE", "SECRET_EXFILTRATION", "SUSPICIOUS_EXFIL_URL"]:
                    score += 0.50
                elif sig_name in ["SYSTEM_PROMPT_OVERRIDE", "JAILBREAK_MODE"]:
                    score += 0.45
                else:
                    score += 0.30

        score = min(1.0, score)
        is_injection = score >= 0.60

        if is_injection:
            logger.warning(
                f"[PromptInjection] Detected threat in node [{node_id}] | "
                f"Signatures: {detected_signatures} | Score: {score:.2f} | "
                f"Snippet: '{snippets[0] if snippets else ''}'"
            )

        return InjectionRiskAssessment(
            risk_score=round(score, 2),
            is_injection=is_injection,
            detected_signatures=detected_signatures,
            matched_text_snippet=snippets[0] if snippets else "",
            raw_text=text,
            source_node_id=node_id,
        )

    def scan_dom_node(self, node: DOMNode) -> InjectionRiskAssessment:
        """
        Scan all text surfaces of a DOM node (text content, attributes, placeholder).
        """
        corpus = f"{node.text_content} {node.attributes.get('title', '')} {node.attributes.get('alt', '')} {node.attributes.get('placeholder', '')} {node.attributes.get('aria-label', '')}"
        return self.scan_text(corpus, node_id=node.node_id)

    def scan_world_model(self, world_model: SanitizedWorldModel) -> Dict[int, InjectionRiskAssessment]:
        """
        Scan entire observed world model and return mapping of tainted node_ids.
        """
        threats: Dict[int, InjectionRiskAssessment] = {}

        # Scan DOM nodes
        for node in world_model.sanitized_dom:
            assessment = self.scan_dom_node(node)
            if assessment.is_injection:
                threats[node.node_id] = assessment

        return threats
