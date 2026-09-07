"""
Local OCR Observer.
Extracts text from screenshots using Tesseract OCR.
Gracefully degrades if Tesseract is not installed.
"""

import base64
import io
import logging
from typing import List, Optional

from webveil.core.models.schema import TextRegion

logger = logging.getLogger("WebVeilOCR")

# Check Tesseract availability at import time
_TESSERACT_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    # Quick check that the tesseract binary exists
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
    logger.info("[OCR] Tesseract OCR is available")
except Exception:
    logger.info("[OCR] Tesseract not available — OCR layer disabled (graceful degradation)")


class OCRObserver:
    """
    Extracts text from screenshots using local Tesseract OCR.
    Falls back silently if Tesseract is not installed.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and _TESSERACT_AVAILABLE

    @property
    def available(self) -> bool:
        return self.enabled

    def extract(self, screenshot_b64: str) -> List[TextRegion]:
        """
        Extract text regions with bounding boxes from a base64 screenshot.
        Returns empty list if OCR is unavailable or fails.
        """
        if not self.enabled or not screenshot_b64:
            return []

        try:
            img_bytes = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_bytes))

            # Use pytesseract to get word-level bounding boxes
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            regions: List[TextRegion] = []
            n_boxes = len(data["text"])

            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = int(data["conf"][i]) if data["conf"][i] != "-1" else 0

                # Filter low-confidence or empty results
                if not text or conf < 40:
                    continue

                region = TextRegion(
                    text=text,
                    bounding_box={
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                    },
                    confidence=conf / 100.0,
                    source="ocr",
                )
                regions.append(region)

            logger.info(f"[OCR] Extracted {len(regions)} text regions from screenshot")
            return regions

        except Exception as e:
            logger.warning(f"[OCR] Text extraction failed: {e}")
            return []

    def extract_full_text(self, screenshot_b64: str) -> str:
        """Extract all text from screenshot as a single string."""
        if not self.enabled or not screenshot_b64:
            return ""

        try:
            img_bytes = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.warning(f"[OCR] Full text extraction failed: {e}")
            return ""
