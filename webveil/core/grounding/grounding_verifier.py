"""
Grounding Verification Engine.
Validates that physical click coordinates and target elements are unobstructed,
interactable, and physically accessible prior to pointer dispatch.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from webveil.core.models.schema import DOMNode

logger = logging.getLogger("WebVeilGrounding.Verifier")


class GroundingVerifier:
    """
    Verifies physical execution preconditions for grounded actions.
    """

    @staticmethod
    def verify_target_interactable(
        node: Optional[DOMNode],
        coords: Optional[Dict[str, float]],
        viewport_size: Tuple[int, int] = (1280, 720),
    ) -> Tuple[bool, str]:
        """
        Check that target node is visible and click coordinates fall inside viewport.
        """
        if node is not None and not node.is_visible:
            return False, f"Target node [{node.node_id}] is marked non-visible in DOM."

        if coords:
            x, y = coords.get("x", 0.0), coords.get("y", 0.0)
            vw, vh = viewport_size
            if x < 0 or x > vw or y < 0 or y > vh:
                return False, f"Target coordinates ({x}, {y}) fall outside active viewport ({vw}x{vh})."

        return True, "Pre-execution target verification passed."

    @staticmethod
    def check_modal_obstruction(
        target_box: Optional[Dict[str, float]],
        active_nodes: List[DOMNode],
    ) -> bool:
        """
        Check if an active modal dialog or overlay is occluding the target box.
        """
        if not target_box:
            return False

        # Find any active modal or dialog nodes
        for node in active_nodes:
            tag = (node.tag_name or "").lower()
            role = node.attributes.get("aria_role", "").lower()
            if (tag == "dialog" or "modal" in role or "dialog" in role) and node.is_visible:
                # Modal is present; if target is not inside the modal, it might be obstructed
                modal_box = node.bounding_box
                if modal_box:
                    mx, my = modal_box.get("x", 0), modal_box.get("y", 0)
                    mw, mh = modal_box.get("width", 0), modal_box.get("height", 0)
                    tx, ty = target_box.get("x", 0), target_box.get("y", 0)
                    # If target is outside the modal boundary, it is occluded by the modal backdrop
                    if not (mx <= tx <= mx + mw and my <= ty <= my + mh):
                        return True
        return False
