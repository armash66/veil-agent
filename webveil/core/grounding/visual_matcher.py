"""
Multimodal Visual Element Matcher.
Correlates proposed browser actions to physical visual screen locations
using text similarity and spatial bounding-box alignment across DOM and OCR.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from webveil.core.models.schema import DOMNode, BrowserAction, TextRegion

logger = logging.getLogger("WebVeilGrounding.VisualMatcher")


@dataclass
class VisualMatchResult:
    matched_node_id: Optional[int]
    bounding_box: Optional[Dict[str, float]]
    confidence: float
    source: str  # "dom", "ocr", "fused"
    label: str


class VisualElementMatcher:
    """
    Finds the exact physical screen location for a proposed action
    by evaluating both DOM nodes and visual OCR regions.
    """

    def match_visual_target(
        self,
        action: BrowserAction,
        dom_nodes: List[DOMNode],
        ocr_regions: Optional[List[TextRegion]] = None,
    ) -> VisualMatchResult:
        """
        Locate physical bounding box for an action.
        """
        ocr_regions = ocr_regions or []

        # Strategy 1: Direct node_id lookup in active DOM
        if action.node_id is not None:
            target_node = next((n for n in dom_nodes if n.node_id == action.node_id), None)
            if target_node:
                bbox = target_node.bounding_box
                conf = 0.90 if bbox else 0.70
                return VisualMatchResult(
                    matched_node_id=target_node.node_id,
                    bounding_box=bbox,
                    confidence=conf,
                    source="dom",
                    label=target_node.text_content or target_node.tag_name,
                )

        # Strategy 2: Text matching across interactive DOM nodes
        search_terms = []
        if action.text:
            search_terms.append(action.text.lower().strip())
        if action.thought:
            # Extract key quoted words if any
            import re
            quotes = re.findall(r'["\'](.*?)["\']', action.thought)
            search_terms.extend([q.lower().strip() for q in quotes if len(q) > 2])

        for term in search_terms:
            # Check DOM interactive nodes
            for node in dom_nodes:
                if node.is_interactive:
                    node_txt = f"{node.text_content} {node.name} {node.attributes.get('placeholder', '')}".lower()
                    if term in node_txt or node_txt in term:
                        return VisualMatchResult(
                            matched_node_id=node.node_id,
                            bounding_box=node.bounding_box,
                            confidence=0.85,
                            source="dom",
                            label=node.text_content,
                        )

            # Check OCR regions (e.g. canvas / image buttons)
            for ocr in ocr_regions:
                if term in ocr.text.lower():
                    return VisualMatchResult(
                        matched_node_id=None,
                        bounding_box=ocr.bounding_box,
                        confidence=round(ocr.confidence * 0.85, 2),
                        source="ocr",
                        label=ocr.text,
                    )

        # No match found
        return VisualMatchResult(
            matched_node_id=action.node_id,
            bounding_box=None,
            confidence=0.0,
            source="none",
            label="",
        )
