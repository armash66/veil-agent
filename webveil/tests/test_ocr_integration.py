"""
REAL OCR Integration Test.
Renders actual PII text into a PIL image, runs it through the real LocalRedactor
and real Tesseract OCR, and asserts the redacted output has NO readable PII
remaining in the pixel data.

This is NOT a mock test. It requires Tesseract to be installed.
If Tesseract is missing, these tests are skipped with a clear message.
"""

import base64
import io
import pytest
from PIL import Image, ImageDraw, ImageFont

# Check if Tesseract is actually available
_TESSERACT_AVAILABLE = False
try:
    import pytesseract
    import shutil
    import os
    if not shutil.which("tesseract"):
        _win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(_win_path):
            pytesseract.pytesseract.tesseract_cmd = _win_path
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
except Exception:
    pass

pytesseract_required = pytest.mark.skipif(
    not _TESSERACT_AVAILABLE,
    reason="Tesseract OCR binary not installed — visual perception tests cannot run"
)

from webveil.core.models.schema import PIIMatch, PIICategory
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.privacy.redactor import LocalRedactor
from webveil.core.vault.client_vault import ClientVault


def render_text_to_b64(text: str, width: int = 400, height: int = 100, font_size: int = 24) -> str:
    """Render text into a real PNG image and return base64-encoded bytes."""
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    # Use default font at readable size — no external font file needed
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (IOError, OSError):
        font = ImageFont.load_default()
    draw.text((20, 30), text, fill=(0, 0, 0), font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def ocr_read_text(b64_image: str) -> str:
    """Run real Tesseract OCR on a base64 image and return all detected text."""
    img_bytes = base64.b64decode(b64_image)
    image = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(image).strip()


@pytesseract_required
class TestRealOCRIntegration:
    """Tests that require real Tesseract OCR to be installed and working."""

    def test_tesseract_can_read_rendered_text(self):
        """Baseline: confirm Tesseract can actually read text we render."""
        test_text = "Hello WebVeil OCR Test"
        b64 = render_text_to_b64(test_text)
        detected = ocr_read_text(b64)
        # Tesseract should detect at least part of the rendered text
        assert "WebVeil" in detected or "OCR" in detected or "Hello" in detected, \
            f"Tesseract failed to read any rendered text. Got: '{detected}'"

    def test_rendered_aadhaar_is_readable_before_redaction(self):
        """Confirm the canary Aadhaar number is visible in the raw image."""
        aadhaar = "1234 5678 9012"
        b64 = render_text_to_b64(f"Aadhaar: {aadhaar}")
        detected = ocr_read_text(b64)
        # At least the digit sequence should be detectable
        assert "1234" in detected or "5678" in detected or "9012" in detected, \
            f"Tesseract couldn't read the rendered Aadhaar. Got: '{detected}'"

    def test_redacted_aadhaar_is_not_readable(self):
        """
        CORE TEST: Render a real Aadhaar number in an image, apply real redaction
        with a bounding box, then re-OCR the output and assert zero PII remains.
        """
        aadhaar_text = "1234 5678 9012"
        b64_raw = render_text_to_b64(f"Aadhaar: {aadhaar_text}", width=400, height=100)

        # Create a PIIMatch with a bounding box covering the text region
        match = PIIMatch(
            category=PIICategory.AADHAAR,
            raw_value=aadhaar_text,
            placeholder="[AADHAAR_1]",
            source_node_id=1,
            bounding_box={"x": 0, "y": 0, "width": 400, "height": 100}
        )

        vault = ClientVault()
        detector = LocalPIIDetector()
        redactor = LocalRedactor(detector=detector, vault=vault)

        # Apply real redaction
        redacted_b64 = redactor.redact_screenshot_b64(b64_raw, [match])

        # Re-OCR the redacted image
        post_redaction_text = ocr_read_text(redacted_b64)

        # Assert the Aadhaar digits are NOT readable anymore
        for digit_group in ["1234", "5678", "9012"]:
            assert digit_group not in post_redaction_text, \
                f"REDACTION FAILURE: '{digit_group}' still readable after redaction. Full OCR output: '{post_redaction_text}'"

    def test_redacted_email_is_not_readable(self):
        """Render a real email, redact, re-OCR, assert email is gone."""
        email = "canary@example.com"
        b64_raw = render_text_to_b64(f"Email: {email}", width=500, height=100)

        match = PIIMatch(
            category=PIICategory.EMAIL,
            raw_value=email,
            placeholder="[EMAIL_1]",
            source_node_id=2,
            bounding_box={"x": 0, "y": 0, "width": 500, "height": 100}
        )

        vault = ClientVault()
        detector = LocalPIIDetector()
        redactor = LocalRedactor(detector=detector, vault=vault)

        redacted_b64 = redactor.redact_screenshot_b64(b64_raw, [match])
        post_text = ocr_read_text(redacted_b64)

        assert "canary" not in post_text.lower(), \
            f"REDACTION FAILURE: 'canary' still readable. Full OCR: '{post_text}'"
        assert "example.com" not in post_text.lower(), \
            f"REDACTION FAILURE: 'example.com' still readable. Full OCR: '{post_text}'"

    def test_partial_bbox_leaves_visible_text(self):
        """
        Negative test: if the redaction box is intentionally too small,
        text SHOULD still be readable — proving our OCR test can actually
        catch redaction failures, not just pass trivially.
        """
        text = "SSN 123-45-6789"
        b64_raw = render_text_to_b64(text, width=400, height=100)

        # Intentionally tiny box that won't cover the text
        match = PIIMatch(
            category=PIICategory.SSN,
            raw_value="123-45-6789",
            placeholder="[SSN_1]",
            source_node_id=3,
            bounding_box={"x": 0, "y": 0, "width": 5, "height": 5}
        )

        vault = ClientVault()
        detector = LocalPIIDetector()
        redactor = LocalRedactor(detector=detector, vault=vault)

        redacted_b64 = redactor.redact_screenshot_b64(b64_raw, [match])
        post_text = ocr_read_text(redacted_b64)

        # Text SHOULD still be partially readable since the box was too small
        has_any_digit = any(d in post_text for d in ["123", "456", "789"])
        assert has_any_digit, \
            f"Negative test failed: OCR couldn't read text even without proper redaction. Got: '{post_text}'"
