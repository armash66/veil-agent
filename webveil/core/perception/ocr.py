"""
OCR Engine wrapper for visual text extraction with bounding boxes.
Provides graceful degradation when Tesseract is not installed locally.
"""

import base64
import io
import os
import shutil
import logging
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import TextRegion

logger = logging.getLogger("WebVeilPerception.OCR")

_TESSERACT_AVAILABLE = False
_PYTESSERACT = None
_PIL_IMAGE = None

try:
    import pytesseract
    from PIL import Image

    # Check for Tesseract binary in PATH or common Windows locations
    if not shutil.which("tesseract"):
        win_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        ]
        for wp in win_paths:
            if os.path.isfile(wp):
                pytesseract.pytesseract.tesseract_cmd = wp
                break

    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
    _PYTESSERACT = pytesseract
    _PIL_IMAGE = Image
    logger.info("[OCR] Tesseract OCR is available.")
except Exception:
    logger.info("[OCR] Tesseract OCR not available. Gracefully degrading to DOM/A11y perception.")


class OCREngine:
    """
    Visual OCR engine extracting text regions and bounding boxes from screenshots.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and _TESSERACT_AVAILABLE

    @property
    def available(self) -> bool:
        return self.enabled

    def extract(self, screenshot_b64: str, min_confidence: float = 30.0) -> List[TextRegion]:
        """
        Extract text regions with normalized bounding boxes from a base64 screenshot.
        Returns: List of TextRegion objects sorted spatially.
        """
        if not self.enabled or not screenshot_b64 or not _PYTESSERACT or not _PIL_IMAGE:
            return []

        try:
            img_bytes = base64.b64decode(screenshot_b64)
            image = _PIL_IMAGE.open(io.BytesIO(img_bytes))

            # Run detailed bounding-box OCR
            ocr_data = _PYTESSERACT.image_to_data(
                image,
                output_type=_PYTESSERACT.Output.DICT,
                config="--psm 11",  # Sparse text with OSD
            )

            regions: List[TextRegion] = []
            n_boxes = len(ocr_data.get("text", []))

            for i in range(n_boxes):
                text = (ocr_data["text"][i] or "").strip()
                try:
                    conf = float(ocr_data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1.0

                if not text or conf < min_confidence or len(text) < 2:
                    continue

                bbox = {
                    "x": float(ocr_data["left"][i]),
                    "y": float(ocr_data["top"][i]),
                    "width": float(ocr_data["width"][i]),
                    "height": float(ocr_data["height"][i]),
                }

                regions.append(TextRegion(
                    text=text,
                    bounding_box=bbox,
                    confidence=round(conf / 100.0, 3),
                    source="ocr",
                ))

            # Spatial sort: top-to-bottom then left-to-right
            regions.sort(key=lambda r: (round(r.bounding_box["y"] / 20.0), r.bounding_box["x"]))
            return regions

        except Exception as e:
            logger.warning(f"[OCR] Text extraction failed: {e}")
            return []

    def ocr_to_summary(self, regions: List[TextRegion], max_regions: int = 40) -> str:
        """
        Build compact token-efficient text summary of OCR regions.
        """
        if not regions:
            return ""

        lines = ["[Visual Text Detected via OCR]"]
        for r in regions[:max_regions]:
            x = int(r.bounding_box.get("x", 0))
            y = int(r.bounding_box.get("y", 0))
            lines.append(f"  ({x},{y}): \"{r.text}\" (conf: {r.confidence:.2f})")

        if len(regions) > max_regions:
            lines.append(f"  ... and {len(regions) - max_regions} more visual text regions.")

        return "\n".join(lines)
