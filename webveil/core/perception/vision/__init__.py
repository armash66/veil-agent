"""
WebVeil Browser-Local Vision Package.
"""

from webveil.core.perception.vision.base import LocalVisionModel, VisionModelMetadata
from webveil.core.perception.vision.ui_detector import LightweightUIVisionModel
from webveil.core.perception.vision.runtime import LocalVisionRuntime

__all__ = [
    "LocalVisionModel",
    "VisionModelMetadata",
    "LightweightUIVisionModel",
    "LocalVisionRuntime",
]
