"""
Coordinate Mapping Engine for Visual Grounding.
Maps DOM and OCR bounding boxes to physical viewport click coordinates,
adjusts for scroll offsets, and verifies viewport boundaries.
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger("WebVeilGrounding.CoordinateMapper")


class CoordinateMapper:
    """
    Transforms bounding boxes into physical screen coordinates
    for robotic and pointer browser interaction.
    """

    @staticmethod
    def get_element_center(bounding_box: Optional[Dict[str, float]]) -> Optional[Tuple[float, float]]:
        """Calculate center coordinate (center_x, center_y) of bounding box."""
        if not bounding_box:
            return None

        x = bounding_box.get("x", 0.0)
        y = bounding_box.get("y", 0.0)
        w = bounding_box.get("width", 0.0)
        h = bounding_box.get("height", 0.0)

        if w <= 0 or h <= 0:
            return (round(x, 1), round(y, 1))

        center_x = round(x + (w / 2.0), 1)
        center_y = round(y + (h / 2.0), 1)
        return (center_x, center_y)

    @staticmethod
    def map_to_viewport(
        point: Tuple[float, float],
        scroll_offset: Tuple[float, float] = (0.0, 0.0),
    ) -> Tuple[float, float]:
        """
        Translate document-relative coordinates to current viewport coordinates.
        viewport_x = doc_x - scroll_x
        viewport_y = doc_y - scroll_y
        """
        px, py = point
        sx, sy = scroll_offset
        return (round(px - sx, 1), round(py - sy, 1))

    @staticmethod
    def is_in_viewport(
        point: Tuple[float, float],
        viewport_size: Tuple[int, int] = (1280, 720),
    ) -> bool:
        """
        Check if point lies within active visible viewport.
        """
        x, y = point
        vw, vh = viewport_size
        return 0.0 <= x <= vw and 0.0 <= y <= vh

    @staticmethod
    def compute_safe_click_point(
        bounding_box: Optional[Dict[str, float]],
        scroll_offset: Tuple[float, float] = (0.0, 0.0),
        viewport_size: Tuple[int, int] = (1280, 720),
    ) -> Dict[str, Any]:
        """
        Computes calibrated click coordinate dictionary:
        { "x": float, "y": float, "is_in_viewport": bool, "raw_center": (x, y) }
        """
        if not bounding_box:
            return {"x": 0.0, "y": 0.0, "is_in_viewport": False, "raw_center": None}

        center = CoordinateMapper.get_element_center(bounding_box)
        if not center:
            return {"x": 0.0, "y": 0.0, "is_in_viewport": False, "raw_center": None}

        vp_point = CoordinateMapper.map_to_viewport(center, scroll_offset)
        in_vp = CoordinateMapper.is_in_viewport(vp_point, viewport_size)

        return {
            "x": vp_point[0],
            "y": vp_point[1],
            "is_in_viewport": in_vp,
            "raw_center": center,
        }
