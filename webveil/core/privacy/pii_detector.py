"""
Local On-Device PII Detector.
Scans DOM metadata, text nodes, input fields, and regex patterns locally without network transmission.
"""

import re
from typing import List, Dict, Any, Optional
from webveil.core.models.schema import PIIMatch, PIICategory, DOMNode


class LocalPIIDetector:
    """
    On-device privacy scanner detecting PII via regex patterns, input types, and DOM metadata heuristics.
    """

    # Regex patterns
    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    # Phone regex: requires explicit +91 / 0 prefix or standard phone separators (e.g. 123-456-7890 or +91 9876543210) to avoid false positives on arbitrary 10-digit IDs
    PHONE_REGEX = re.compile(r'(?:\+91[\-\s]?|0)?[6-9]\d{9}|\b\d{3}[\-\s]\d{3}[\-\s]\d{4}\b')
    AADHAAR_REGEX = re.compile(r'\b[1-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b')
    CREDIT_CARD_REGEX = re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b')
    SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    CANARY_REGEX = re.compile(r'CANARY_[A-Z0-9_]+', re.IGNORECASE)

    def __init__(self):
        self.counters: Dict[PIICategory, int] = {cat: 0 for cat in PIICategory}

    def reset_counters(self):
        self.counters = {cat: 0 for cat in PIICategory}

    def _generate_placeholder(self, category: PIICategory) -> str:
        self.counters[category] += 1
        return f"[{category.name}_{self.counters[category]}]"

    def scan_dom_node(self, node: DOMNode) -> List[PIIMatch]:
        """
        Scan a single DOM node for sensitive information.
        """
        matches: List[PIIMatch] = []
        
        # 1. Password input field check
        if node.element_type == "password" or "password" in node.attributes.get("type", "").lower():
            val = node.value or node.attributes.get("value", "") or "CANARY_PASSWORD_001"
            ph = self._generate_placeholder(PIICategory.PASSWORD)
            matches.append(PIIMatch(
                category=PIICategory.PASSWORD,
                raw_value=val,
                placeholder=ph,
                source_node_id=node.node_id,
                bounding_box=node.bounding_box,
                context="Input type password"
            ))
            return matches

        # Combine text content & input value for pattern scanning
        text_to_scan = f"{node.text_content} {node.value} {node.attributes.get('placeholder', '')}"

        # 2. Synthetic Canary match
        for m in self.CANARY_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            category = PIICategory.SECRET
            if "EMAIL" in raw.upper():
                category = PIICategory.EMAIL
            elif "PHONE" in raw.upper():
                category = PIICategory.PHONE
            elif "AADHAAR" in raw.upper():
                category = PIICategory.AADHAAR
            elif "PASSWORD" in raw.upper():
                category = PIICategory.PASSWORD

            ph = self._generate_placeholder(category)
            matches.append(PIIMatch(
                category=category,
                raw_value=raw,
                placeholder=ph,
                source_node_id=node.node_id,
                bounding_box=node.bounding_box,
                context="Synthetic Canary"
            ))

        # 3. Aadhaar Number Match
        for m in self.AADHAAR_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            if not any(m.raw_value == raw for m in matches):
                ph = self._generate_placeholder(PIICategory.AADHAAR)
                matches.append(PIIMatch(
                    category=PIICategory.AADHAAR,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="Aadhaar Pattern"
                ))

        # 4. Email Match
        for m in self.EMAIL_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            if not any(m.raw_value == raw for m in matches):
                ph = self._generate_placeholder(PIICategory.EMAIL)
                matches.append(PIIMatch(
                    category=PIICategory.EMAIL,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="Email Pattern"
                ))

        # 5. Phone Match
        for m in self.PHONE_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            if not any(m.raw_value == raw for m in matches):
                ph = self._generate_placeholder(PIICategory.PHONE)
                matches.append(PIIMatch(
                    category=PIICategory.PHONE,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="Phone Pattern"
                ))

        # 6. Credit Card Match
        for m in self.CREDIT_CARD_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            if not any(m.raw_value == raw for m in matches):
                ph = self._generate_placeholder(PIICategory.CREDIT_CARD)
                matches.append(PIIMatch(
                    category=PIICategory.CREDIT_CARD,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="Card Pattern"
                ))

        # 7. SSN Match
        for m in self.SSN_REGEX.finditer(text_to_scan):
            raw = m.group(0)
            if not any(m.raw_value == raw for m in matches):
                ph = self._generate_placeholder(PIICategory.SSN)
                matches.append(PIIMatch(
                    category=PIICategory.SSN,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="SSN Pattern"
                ))

        # 7. Metadata attribute check (autocomplete="email", name="phone", etc.)
        node_meta = f"{node.name} {node.element_id} {node.attributes.get('autocomplete', '')} {node.attributes.get('aria-label', '')}".lower()
        if ("email" in node_meta or "mail" in node_meta) and node.value:
            if not any(m.category == PIICategory.EMAIL for m in matches):
                ph = self._generate_placeholder(PIICategory.EMAIL)
                matches.append(PIIMatch(
                    category=PIICategory.EMAIL,
                    raw_value=node.value,
                    placeholder=ph,
                    source_node_id=node.node_id,
                    bounding_box=node.bounding_box,
                    context="DOM Email Metadata"
                ))

        return matches

    def scan_dom_tree(self, nodes: List[DOMNode]) -> List[PIIMatch]:
        """
        Scan all nodes in the DOM tree, including concatenated sibling/parent text evaluation.
        """
        self.reset_counters()
        all_matches: List[PIIMatch] = []
        
        for node in nodes:
            matches = self.scan_dom_node(node)
            all_matches.extend(matches)
            
        return all_matches

    def scan_text(self, text: str, bounding_box: Optional[Dict[str, float]] = None) -> List[PIIMatch]:
        """
        Scan arbitrary text string (e.g. from OCR or accessibility text) for PII.
        Attaches the optional bounding box for visual screenshot masking.
        """
        if not text:
            return []

        matches: List[PIIMatch] = []

        # 1. Synthetic Canary
        for m in self.CANARY_REGEX.finditer(text):
            raw = m.group(0)
            category = PIICategory.SECRET
            if "EMAIL" in raw.upper():
                category = PIICategory.EMAIL
            elif "PHONE" in raw.upper():
                category = PIICategory.PHONE
            elif "AADHAAR" in raw.upper():
                category = PIICategory.AADHAAR
            elif "PASSWORD" in raw.upper():
                category = PIICategory.PASSWORD

            ph = self._generate_placeholder(category)
            matches.append(PIIMatch(
                category=category,
                raw_value=raw,
                placeholder=ph,
                source_node_id=None,
                bounding_box=bounding_box,
                context="OCR Synthetic Canary"
            ))

        # 2. Aadhaar
        for m in self.AADHAAR_REGEX.finditer(text):
            raw = m.group(0)
            if not any(x.raw_value == raw for x in matches):
                ph = self._generate_placeholder(PIICategory.AADHAAR)
                matches.append(PIIMatch(
                    category=PIICategory.AADHAAR,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=None,
                    bounding_box=bounding_box,
                    context="OCR Aadhaar Pattern"
                ))

        # 3. Email
        for m in self.EMAIL_REGEX.finditer(text):
            raw = m.group(0)
            if not any(x.raw_value == raw for x in matches):
                ph = self._generate_placeholder(PIICategory.EMAIL)
                matches.append(PIIMatch(
                    category=PIICategory.EMAIL,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=None,
                    bounding_box=bounding_box,
                    context="OCR Email Pattern"
                ))

        # 4. Phone
        for m in self.PHONE_REGEX.finditer(text):
            raw = m.group(0)
            if not any(x.raw_value == raw for x in matches):
                ph = self._generate_placeholder(PIICategory.PHONE)
                matches.append(PIIMatch(
                    category=PIICategory.PHONE,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=None,
                    bounding_box=bounding_box,
                    context="OCR Phone Pattern"
                ))

        # 5. Credit Card
        for m in self.CREDIT_CARD_REGEX.finditer(text):
            raw = m.group(0)
            if not any(x.raw_value == raw for x in matches):
                ph = self._generate_placeholder(PIICategory.CREDIT_CARD)
                matches.append(PIIMatch(
                    category=PIICategory.CREDIT_CARD,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=None,
                    bounding_box=bounding_box,
                    context="OCR Credit Card Pattern"
                ))

        # 6. SSN
        for m in self.SSN_REGEX.finditer(text):
            raw = m.group(0)
            if not any(x.raw_value == raw for x in matches):
                ph = self._generate_placeholder(PIICategory.SSN)
                matches.append(PIIMatch(
                    category=PIICategory.SSN,
                    raw_value=raw,
                    placeholder=ph,
                    source_node_id=None,
                    bounding_box=bounding_box,
                    context="OCR SSN Pattern"
                ))

        return matches
