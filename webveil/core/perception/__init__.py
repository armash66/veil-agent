"""
WebVeil Multimodal Perception Subsystem.
Provides local extraction, spatial fusion, and enrichment across
DOM, Accessibility, Screenshots, and OCR.
"""

from webveil.core.perception.screenshot import ScreenshotCapture
from webveil.core.perception.accessibility import AccessibilityExtractor
from webveil.core.perception.ocr import OCREngine
from webveil.core.perception.fusion import MultimodalFusionEngine
from webveil.core.perception.pipeline import MultimodalPerceptionPipeline

__all__ = [
    "ScreenshotCapture",
    "AccessibilityExtractor",
    "OCREngine",
    "MultimodalFusionEngine",
    "MultimodalPerceptionPipeline",
]
