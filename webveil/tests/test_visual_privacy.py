"""
Unit tests for Visual Privacy & Sensitive Region Redactor.
Tests on-device detection of sensitive visual objects (ID cards, payment cards, QR codes),
solid blackout masking, and fail-closed privacy guarantees.
"""

import io
import base64
import unittest
from PIL import Image, ImageDraw

from webveil.core.models.schema import VisualRegion, TextRegion
from webveil.core.privacy.visual_privacy import VisualPrivacyEngine, VisualSensitiveCategory


class TestVisualPrivacy(unittest.TestCase):

    def setUp(self):
        self.engine = VisualPrivacyEngine()

    def _create_sample_screenshot(self) -> str:
        """Create a simple white screenshot and return base64."""
        img = Image.new("RGB", (400, 300), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def test_visual_redaction_applied_on_sensitive_content(self):
        """Verify solid black mask is drawn over sensitive OCR and visual regions."""
        b64 = self._create_sample_screenshot()

        # Sensitive OCR regions
        ocr_regions = [
            TextRegion(
                text="Aadhaar Card: 9988 7766 5544",
                bounding_box={"x": 50, "y": 50, "width": 150, "height": 30},
                confidence=0.95
            ),
            TextRegion(
                text="CVV: 789 Valid Thru 12/28",
                bounding_box={"x": 50, "y": 120, "width": 120, "height": 25},
                confidence=0.92
            ),
        ]

        visual_regions = [
            VisualRegion(
                region_id="vis_priv_1",
                region_type="sensitive_candidate",
                bounding_box={"x": 250, "y": 50, "width": 100, "height": 80},
                confidence=0.88,
                label="Private User Profile Photo"
            )
        ]

        redacted_b64, records = self.engine.detect_and_redact(b64, visual_regions, ocr_regions)

        # Assertions
        self.assertEqual(len(records), 3)
        self.assertTrue(bool(redacted_b64))

        # Check categories
        categories = [r.category for r in records]
        self.assertIn(VisualSensitiveCategory.IDENTITY_DOCUMENT, categories)
        self.assertIn(VisualSensitiveCategory.PAYMENT_CARD, categories)
        self.assertIn(VisualSensitiveCategory.PRIVATE_PROFILE, categories)

        # Verify pixels in redacted area are solid black (0, 0, 0)
        redacted_bytes = base64.b64decode(redacted_b64)
        redacted_img = Image.open(io.BytesIO(redacted_bytes))
        # Pixel inside first redacted box (x=60, y=60)
        pixel = redacted_img.getpixel((60, 60))
        self.assertEqual(pixel, (0, 0, 0))

    def test_fail_closed_on_corrupt_image(self):
        """Verify engine fails closed (returns empty string) if image decoding fails."""
        corrupt_b64 = "NOT_A_VALID_IMAGE_BASE64_DATA"
        ocr_regions = [
            TextRegion(
                text="Aadhaar: 1234 5678 9012",
                bounding_box={"x": 10, "y": 10, "width": 50, "height": 20}
            )
        ]

        redacted_b64, records = self.engine.detect_and_redact(corrupt_b64, [], ocr_regions)
        # Empty string returned so unredacted content is never leaked
        self.assertEqual(redacted_b64, "")
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
