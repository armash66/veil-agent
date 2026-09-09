"""
Screenshot capture and format normalization.
Handles viewport and full-page capture, dimension extraction, and zero-PII handling.
"""

import base64
import io
import logging
from typing import Tuple, Optional

logger = logging.getLogger("WebVeilPerception.Screenshot")

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class ScreenshotCapture:
    """
    Manages local screenshot capture, dimension inspection,
    and format normalization for multimodal perception.
    """

    @staticmethod
    def capture_viewport(page) -> Tuple[Optional[bytes], str, int, int]:
        """
        Capture current viewport screenshot.
        Returns: (raw_bytes, base64_str, width, height)
        """
        if not page:
            return None, "", 0, 0

        try:
            raw_bytes = page.screenshot(type="png", full_page=False)
            b64_str = base64.b64encode(raw_bytes).decode("utf-8")
            width, height = ScreenshotCapture.get_dimensions(b64_str)
            return raw_bytes, b64_str, width, height
        except Exception as e:
            logger.warning(f"[Screenshot] Viewport capture failed: {e}")
            return None, "", 0, 0

    @staticmethod
    def capture_full_page(page) -> Tuple[Optional[bytes], str, int, int]:
        """
        Capture complete full-page screenshot.
        Returns: (raw_bytes, base64_str, width, height)
        """
        if not page:
            return None, "", 0, 0

        try:
            raw_bytes = page.screenshot(type="png", full_page=True)
            b64_str = base64.b64encode(raw_bytes).decode("utf-8")
            width, height = ScreenshotCapture.get_dimensions(b64_str)
            return raw_bytes, b64_str, width, height
        except Exception as e:
            logger.warning(f"[Screenshot] Full-page capture failed: {e}")
            return None, "", 0, 0

    @staticmethod
    def get_dimensions(screenshot_b64: str) -> Tuple[int, int]:
        """
        Extract (width, height) from base64 PNG/JPEG image without loading full uncompressed buffer.
        """
        if not screenshot_b64 or not _PIL_AVAILABLE:
            return 0, 0

        try:
            img_bytes = base64.b64decode(screenshot_b64)
            with Image.open(io.BytesIO(img_bytes)) as img:
                return img.size  # (width, height)
        except Exception as e:
            logger.debug(f"[Screenshot] Failed to read dimensions: {e}")
            return 0, 0

    @staticmethod
    def resize_if_needed(screenshot_b64: str, max_dimension: int = 1920) -> Tuple[str, int, int]:
        """
        Resize image proportionally if width or height exceeds max_dimension to conserve memory and tokens.
        """
        if not screenshot_b64 or not _PIL_AVAILABLE:
            return screenshot_b64, 0, 0

        try:
            img_bytes = base64.b64decode(screenshot_b64)
            with Image.open(io.BytesIO(img_bytes)) as img:
                w, h = img.size
                if w <= max_dimension and h <= max_dimension:
                    return screenshot_b64, w, h

                scale = min(max_dimension / w, max_dimension / h)
                new_w, new_h = int(w * scale), int(h * scale)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                buf = io.BytesIO()
                resized.save(buf, format="PNG", optimize=True)
                new_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                return new_b64, new_w, new_h
        except Exception as e:
            logger.warning(f"[Screenshot] Resize failed: {e}")
            return screenshot_b64, 0, 0
