"""
Unit tests for Phase 3: Privacy + OCR Integration.
Verifies OCR text region PII sanitization, tokenization into ClientVault,
visual bounding-box masking on screenshots for OCR regions, and multi-layer WorldModel sanitization.
"""

import io
import base64
import unittest
from PIL import Image, ImageDraw

from webveil.core.models.schema import DOMNode, TextRegion, LocalWorldModel, PIICategory
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.vault.client_vault import ClientVault
from webveil.core.privacy.redactor import LocalRedactor
from webveil.core.observation.world_model import WorldModelBuilder


class TestPrivacyOCRIntegration(unittest.TestCase):

    def setUp(self):
        self.detector = LocalPIIDetector()
        self.vault = ClientVault()
        self.redactor = LocalRedactor(self.detector, self.vault)
        self.builder = WorldModelBuilder(self.redactor, ocr_enabled=False)

    def _create_sample_screenshot_b64(self, width: int = 400, height: int = 300) -> str:
        """Helper to create a solid white base64 PNG."""
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def test_ocr_region_sanitization_and_vault_storage(self):
        """Verify OCR text regions with PII are redacted and tokens stored in vault."""
        origin = "https://finance.example.com"
        raw_aadhaar = "9876 5432 1098"
        raw_email = "employee@corp.example.com"

        regions = [
            TextRegion(
                text=f"Aadhaar card number is {raw_aadhaar}",
                bounding_box={"x": 50, "y": 60, "width": 180, "height": 24},
                confidence=0.96,
            ),
            TextRegion(
                text=f"Contact email: {raw_email}",
                bounding_box={"x": 50, "y": 120, "width": 200, "height": 22},
                confidence=0.94,
            ),
            TextRegion(
                text="Public text without any private data",
                bounding_box={"x": 50, "y": 180, "width": 150, "height": 20},
                confidence=0.99,
            ),
        ]

        sanitized_regions, ocr_matches = self.redactor.sanitize_ocr_regions(regions, origin)

        # 2 PII matches found
        self.assertEqual(len(ocr_matches), 2)
        categories = [m.category for m in ocr_matches]
        self.assertIn(PIICategory.AADHAAR, categories)
        self.assertIn(PIICategory.EMAIL, categories)

        # Ensure raw secrets do NOT exist in sanitized text
        self.assertNotIn(raw_aadhaar, sanitized_regions[0].text)
        self.assertNotIn(raw_email, sanitized_regions[1].text)
        self.assertIn("[AADHAAR_", sanitized_regions[0].text)
        self.assertIn("[EMAIL_", sanitized_regions[1].text)

        # Check vault has entries for these placeholders
        aadhaar_match = [m for m in ocr_matches if m.category == PIICategory.AADHAAR][0]
        email_match = [m for m in ocr_matches if m.category == PIICategory.EMAIL][0]
        self.assertIn(aadhaar_match.placeholder, self.vault._entries)
        self.assertIn(email_match.placeholder, self.vault._entries)
        self.assertEqual(self.vault._entries[aadhaar_match.placeholder].secret, raw_aadhaar)
        self.assertEqual(self.vault._entries[email_match.placeholder].secret, raw_email)

    def test_visual_screenshot_masking_for_ocr_and_dom_regions(self):
        """Verify solid black rectangle masking over both DOM and OCR bounding boxes."""
        raw_b64 = self._create_sample_screenshot_b64(width=300, height=200)

        # Run sanitization with OCR and DOM regions
        dom_node = DOMNode(
            node_id=1,
            tag_name="span",
            text_content="Account: CANARY_SECRET_ALPHA",
            bounding_box={"x": 20, "y": 30, "width": 100, "height": 25},
        )
        ocr_region = TextRegion(
            text="SSN: 123-45-6789",
            bounding_box={"x": 20, "y": 80, "width": 120, "height": 25},
            confidence=0.95,
        )

        _, dom_matches = self.redactor.sanitize_dom([dom_node], "https://example.com")
        _, ocr_matches = self.redactor.sanitize_ocr_regions([ocr_region], "https://example.com")
        all_matches = dom_matches + ocr_matches

        redacted_b64 = self.redactor.redact_screenshot_b64(raw_b64, all_matches)

        # Redacted image must not be empty and must differ from raw white image
        self.assertNotEqual(redacted_b64, raw_b64)
        img_bytes = base64.b64decode(redacted_b64)
        redacted_img = Image.open(io.BytesIO(img_bytes))

        # Check pixel color in masked area (should be dark fill ~(20,20,20))
        # DOM box center is (70, 42)
        pixel_dom = redacted_img.getpixel((70, 42))
        # OCR box center is (80, 92)
        pixel_ocr = redacted_img.getpixel((80, 92))

        # Both centers must be masked (dark pixels, not white 255,255,255)
        self.assertTrue(pixel_dom[0] < 100 and pixel_dom[1] < 100 and pixel_dom[2] < 100)
        self.assertTrue(pixel_ocr[0] < 100 and pixel_ocr[1] < 100 and pixel_ocr[2] < 100)

    def test_world_model_builder_sanitizes_unified_dom_and_ocr(self):
        """Verify WorldModelBuilder.sanitize produces zero raw secrets across all layers."""
        raw_b64 = self._create_sample_screenshot_b64()
        raw_phone = "+91 9876543210"
        raw_card = "4111111111111111"

        local_model = LocalWorldModel(
            url="https://portal.bank.com/profile",
            title="User Profile",
            dom_nodes=[
                DOMNode(
                    node_id=10,
                    tag_name="input",
                    element_type="text",
                    value=raw_phone,
                    bounding_box={"x": 50, "y": 50, "width": 100, "height": 30},
                    is_interactive=True,
                )
            ],
            formatted_dom="<input value='+91 9876543210'/>",
            ocr_regions=[
                TextRegion(
                    text=f"Debit Card: {raw_card}",
                    bounding_box={"x": 50, "y": 150, "width": 160, "height": 30},
                    confidence=0.93,
                )
            ],
            screenshot_b64=raw_b64,
            page_text=f"Profile text with {raw_phone}",
        )

        sanitized, matches, timings = self.builder.sanitize(local_model, "https://portal.bank.com")

        # Must report 2 detected PII items
        self.assertEqual(sanitized.detected_pii_count, 2)
        self.assertEqual(len(matches), 2)

        # No raw phone or card in sanitized DOM or OCR summary
        self.assertNotIn(raw_phone, sanitized.formatted_dom)
        self.assertNotIn(raw_phone, sanitized.sanitized_dom[0].value)
        self.assertNotIn(raw_card, sanitized.ocr_summary)

        # Placeholders must be present
        self.assertIn("[PHONE_", sanitized.formatted_dom)
        self.assertIn("[CREDIT_CARD_", sanitized.ocr_summary)

        # Timings must track both DOM and OCR detection
        self.assertIn("pii_dom_detection_ms", timings)
        self.assertIn("pii_ocr_detection_ms", timings)
        self.assertIn("redaction_ms", timings)


if __name__ == "__main__":
    unittest.main()
