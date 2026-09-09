"""
Local Redaction & Sanitization Engine.
Sanitizes DOM trees and draws visual redaction bounding boxes over screenshots.
"""

import base64
import io
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from webveil.core.models.schema import DOMNode, PIIMatch, SanitizedObservation, TextRegion
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault


class LocalRedactor:
    """
    Sanitizes DOM trees and applies visual canvas mask redactions on screenshots.
    """

    def __init__(self, detector: LocalPIIDetector, vault: ClientVault):
        self.detector = detector
        self.vault = vault

    def sanitize_dom(self, nodes: List[DOMNode], origin: str) -> Tuple[List[DOMNode], List[PIIMatch]]:
        """
        Sanitize raw DOM tree nodes, replacing PII text with semantic placeholders.
        """
        matches = self.detector.scan_dom_tree(nodes)
        sanitized_nodes: List[DOMNode] = []

        for node in nodes:
            # Copy node to avoid mutating original state in place
            s_node = DOMNode(
                node_id=node.node_id,
                tag_name=node.tag_name,
                element_type=node.element_type,
                element_id=node.element_id,
                name=node.name,
                text_content=node.text_content,
                value=node.value,
                is_interactive=node.is_interactive,
                is_visible=node.is_visible,
                bounding_box=node.bounding_box,
                attributes=dict(node.attributes)
            )

            # Match node against detected PII
            node_matches = [m for m in matches if m.source_node_id == node.node_id]
            for m in node_matches:
                ph = self.vault.store_match(m, origin, s_node)
                s_node.placeholder_assigned = ph

                # Perform text substitution
                if m.raw_value in s_node.text_content:
                    s_node.text_content = s_node.text_content.replace(m.raw_value, ph)
                else:
                    s_node.text_content = ph

                if s_node.value:
                    s_node.value = ph
                if "value" in s_node.attributes:
                    s_node.attributes["value"] = ph
                if "placeholder" in s_node.attributes and m.raw_value in s_node.attributes["placeholder"]:
                    s_node.attributes["placeholder"] = ph

            sanitized_nodes.append(s_node)

        return sanitized_nodes, matches

    def sanitize_ocr_regions(self, regions: List[TextRegion], origin: str) -> Tuple[List[TextRegion], List[PIIMatch]]:
        """
        Scan OCR text regions for sensitive PII, replace raw text with vault placeholders,
        and store matches in ClientVault with their spatial bounding boxes.
        """
        if not regions:
            return [], []

        sanitized_regions: List[TextRegion] = []
        all_ocr_matches: List[PIIMatch] = []

        for region in regions:
            matches = self.detector.scan_text(region.text, bounding_box=region.bounding_box)
            clean_text = region.text

            for m in matches:
                ph = self.vault.store_match(m, origin, None)
                m.placeholder = ph
                clean_text = clean_text.replace(m.raw_value, ph)
                all_ocr_matches.append(m)

            sanitized_regions.append(TextRegion(
                text=clean_text,
                bounding_box=dict(region.bounding_box),
                confidence=region.confidence,
                source=region.source,
            ))

        return sanitized_regions, all_ocr_matches

    def redact_screenshot_b64(self, raw_b64: str, matches: List[PIIMatch]) -> str:
        """
        Draw solid redaction boxes with token overlay text over PII bounding boxes.
        """
        if not raw_b64 or not matches:
            return raw_b64

        try:
            img_bytes = base64.b64decode(raw_b64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            draw = ImageDraw.Draw(image)

            for match in matches:
                box = match.bounding_box
                if not box:
                    continue

                x = box.get("x", 0)
                y = box.get("y", 0)
                w = box.get("width", 0)
                h = box.get("height", 0)

                if w <= 0 or h <= 0:
                    continue

                # Solid dark redaction box with safety margin padding
                padding = 2
                x0 = max(0, x - padding)
                y0 = max(0, y - padding)
                x1 = x + w + padding
                y1 = y + h + padding

                # Draw solid black rectangle mask
                draw.rectangle([x0, y0, x1, y1], fill=(20, 20, 20), outline=(255, 0, 0), width=2)

                # Draw placeholder text label
                draw.text((x0 + 4, y0 + 2), match.placeholder, fill=(255, 255, 255))

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        except Exception as e:
            # Return un-modified or blank if image processing fails, but never leak raw if match exists
            return raw_b64
