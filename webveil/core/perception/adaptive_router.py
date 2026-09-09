"""
Resource-Aware Adaptive Perception Router.
Evaluates browser state complexity to dynamically decide whether DOM + A11y
is sufficient or if expensive Screenshot + OCR must be activated.
Implements SIH PS 26171 Resource & Latency Optimization.
"""

import logging
from enum import Enum
from typing import List, Optional, Tuple
from webveil.core.models.schema import DOMNode

logger = logging.getLogger("WebVeilPerception.Adaptive")


class PerceptionModality(str, Enum):
    DOM_A11Y_FAST = "DOM_A11Y_FAST"           # ~10-30ms: pure semantic DOM & accessibility
    MULTIMODAL_FULL = "MULTIMODAL_FULL"       # ~150-300ms: screenshot + OCR + spatial fusion
    CANVAS_VISION = "CANVAS_VISION"           # ~300-500ms: deep visual inspection for non-DOM canvases


class AdaptivePerceptionRouter:
    """
    Decides the minimal necessary perception modality for a given page state and user task.
    Prevents running expensive screenshot capture and OCR when standard DOM + A11y is sufficient.
    """

    def __init__(self, forced_mode: Optional[PerceptionModality] = None):
        self.forced_mode = forced_mode

    def determine_modality(
        self,
        dom_nodes: List[DOMNode],
        page_has_canvas: bool = False,
        user_task: str = "",
    ) -> Tuple[PerceptionModality, str]:
        """
        Analyze page state and determine whether visual capture is strictly necessary.
        Returns (PerceptionModality, reason).
        """
        if self.forced_mode:
            return self.forced_mode, f"Forced modality override: {self.forced_mode.value}"

        # Criterion 1: Canvas Elements Present
        # Canvas elements do not expose DOM text or semantics -> Requires Visual OCR
        if page_has_canvas or any(n.tag_name == "canvas" for n in dom_nodes):
            return (
                PerceptionModality.CANVAS_VISION,
                "Page contains <canvas> element without DOM text; requires visual perception."
            )

        # Criterion 2: Low DOM Density / Missing Interactive Labels
        # If there are very few DOM nodes or interactive elements have no text/aria labels
        interactive_nodes = [n for n in dom_nodes if n.is_interactive]
        unlabeled_interactive = [
            n for n in interactive_nodes
            if not n.text_content
            and not n.attributes.get("aria-label")
            and not n.attributes.get("title")
            and not n.attributes.get("placeholder")
            and not n.attributes.get("name")
            and not n.value
        ]

        if interactive_nodes and (len(unlabeled_interactive) / len(interactive_nodes) > 0.40):
            return (
                PerceptionModality.MULTIMODAL_FULL,
                "Significant fraction (>40%) of interactive elements lack text/ARIA/placeholder labels; requires OCR/Screenshot."
            )

        # Criterion 3: Visual / Image-Heavy Task Keywords
        task_lower = user_task.lower()
        if any(w in task_lower for w in ["canvas", "chart", "graph", "diagram", "visual", "image", "look at"]):
            return (
                PerceptionModality.MULTIMODAL_FULL,
                "User task explicitly refers to visual content (chart/graph/image/canvas)."
            )

        # Default: Standard DOM + A11y is fully sufficient
        return (
            PerceptionModality.DOM_A11Y_FAST,
            f"DOM and accessibility hierarchy are rich ({len(dom_nodes)} nodes, {len(interactive_nodes)} interactive); fast path active."
        )
