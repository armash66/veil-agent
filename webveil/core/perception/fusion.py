"""
Multimodal Spatial Fusion Engine.
Fuses DOM nodes, accessibility tree semantics, and OCR text into
a unified spatial representation with bounding box correlation.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from webveil.core.models.schema import DOMNode, TextRegion

logger = logging.getLogger("WebVeilPerception.Fusion")


@dataclass
class FusedPerceptionResult:
    """Result of multimodal spatial fusion across DOM, A11y, and OCR."""
    dom_nodes: List[DOMNode]
    matched_ocr_count: int = 0
    unmatched_ocr_regions: List[TextRegion] = field(default_factory=list)
    enriched_node_count: int = 0
    spatial_coverage_ratio: float = 0.0


class MultimodalFusionEngine:
    """
    Fuses DOM nodes, accessibility tree information, and OCR text
    into a unified spatial world model.
    """

    @staticmethod
    def compute_iou(b1: Dict[str, float], b2: Dict[str, float]) -> float:
        """Calculate 2D Intersection over Union (IoU) of two bounding boxes."""
        if not b1 or not b2:
            return 0.0

        x1 = max(b1.get("x", 0), b2.get("x", 0))
        y1 = max(b1.get("y", 0), b2.get("y", 0))
        x2 = min(b1.get("x", 0) + b1.get("width", 0), b2.get("x", 0) + b2.get("width", 0))
        y2 = min(b1.get("y", 0) + b1.get("height", 0), b2.get("y", 0) + b2.get("height", 0))

        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if intersection <= 0:
            return 0.0

        area1 = b1.get("width", 0) * b1.get("height", 0)
        area2 = b2.get("width", 0) * b2.get("height", 0)
        union = area1 + area2 - intersection

        return round(intersection / union, 4) if union > 0 else 0.0

    @staticmethod
    def is_contained(inner: Dict[str, float], outer: Dict[str, float], tolerance: float = 5.0) -> bool:
        """Check if inner bounding box is substantially contained within outer bounding box."""
        if not inner or not outer:
            return False

        ix1, iy1 = inner.get("x", 0), inner.get("y", 0)
        ix2 = ix1 + inner.get("width", 0)
        iy2 = iy1 + inner.get("height", 0)

        ox1, oy1 = outer.get("x", 0) - tolerance, outer.get("y", 0) - tolerance
        ox2 = outer.get("x", 0) + outer.get("width", 0) + tolerance
        oy2 = outer.get("y", 0) + outer.get("height", 0) + tolerance

        return ox1 <= ix1 and ix2 <= ox2 and oy1 <= iy1 and iy2 <= oy2

    def fuse(
        self,
        dom_nodes: List[DOMNode],
        a11y_tree: Optional[Dict[str, Any]],
        ocr_regions: List[TextRegion],
    ) -> FusedPerceptionResult:
        """
        Cross-reference OCR regions and A11y data with DOM nodes.
        Enriches DOM nodes with missing visual text and semantic roles.
        """
        if not dom_nodes:
            return FusedPerceptionResult(
                dom_nodes=[],
                matched_ocr_count=0,
                unmatched_ocr_regions=ocr_regions,
                enriched_node_count=0,
            )

        matched_ocr_indices = set()
        enriched_count = 0

        # Step 1: Spatial alignment between OCR and DOM nodes
        for node in dom_nodes:
            node_box = node.bounding_box
            if not node_box:
                continue

            # Check for overlapping or contained OCR text
            matched_texts = []
            for idx, ocr in enumerate(ocr_regions):
                ocr_box = ocr.bounding_box
                if self.is_contained(ocr_box, node_box) or self.compute_iou(node_box, ocr_box) > 0.3:
                    matched_texts.append(ocr.text)
                    matched_ocr_indices.add(idx)

            if matched_texts:
                combined_ocr_text = " ".join(matched_texts).strip()
                if not node.text_content or len(node.text_content.strip()) == 0:
                    node.text_content = combined_ocr_text
                    node.attributes["visual_ocr_text"] = combined_ocr_text
                    enriched_count += 1
                elif combined_ocr_text.lower() not in node.text_content.lower():
                    node.attributes["visual_ocr_text"] = combined_ocr_text
                    enriched_count += 1

        # Step 2: Semantic alignment with A11y flat tree
        if a11y_tree:
            from webveil.core.perception.accessibility import AccessibilityExtractor
            extractor = AccessibilityExtractor()
            flat_a11y = extractor.flatten_interactive_nodes(a11y_tree)

            # Match interactive DOM nodes by text/name
            for node in dom_nodes:
                if not node.is_interactive:
                    continue
                node_text = (node.text_content or "").strip().lower()
                for item in flat_a11y:
                    item_name = item.get("name", "").strip().lower()
                    if item_name and (item_name == node_text or item_name in node_text):
                        if "aria_role" not in node.attributes:
                            node.attributes["aria_role"] = item.get("role", "")
                            if item.get("description"):
                                node.attributes["aria_desc"] = item["description"]
                            enriched_count += 1
                        break

        unmatched = [ocr for i, ocr in enumerate(ocr_regions) if i not in matched_ocr_indices]

        return FusedPerceptionResult(
            dom_nodes=dom_nodes,
            matched_ocr_count=len(matched_ocr_indices),
            unmatched_ocr_regions=unmatched,
            enriched_node_count=enriched_count,
            spatial_coverage_ratio=round(len(matched_ocr_indices) / max(1, len(ocr_regions)), 3),
        )
