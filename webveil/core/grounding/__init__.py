"""
WebVeil Visual Grounding Subsystem.
Provides element grounding, physical coordinate mapping,
multimodal visual element matching, and pre-execution grounding verification.
"""

from webveil.core.grounding.element_grounder import ElementGrounder
from webveil.core.grounding.coordinate_mapper import CoordinateMapper
from webveil.core.grounding.visual_matcher import VisualElementMatcher, VisualMatchResult
from webveil.core.grounding.grounding_verifier import GroundingVerifier

__all__ = [
    "ElementGrounder",
    "CoordinateMapper",
    "VisualElementMatcher",
    "VisualMatchResult",
    "GroundingVerifier",
]
