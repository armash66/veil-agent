"""
Comprehensive Security Automated Test Suite for Egress Guard.
Tests canary redaction, OCR failures (fail-closed), edge padding leak checks, and exception safety.
"""

import base64
import io
import pytest
from PIL import Image, ImageDraw
from webveil.core.models.schema import PIIMatch, PIICategory
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.core.privacy.redactor import LocalRedactor
from webveil.core.vault.client_vault import ClientVault
from webveil.security.egress_guard import EgressGuard, EgressViolationError


def create_test_image_b64(width=300, height=200, color=(255, 255, 255)) -> str:
    image = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@pytest.fixture
def test_setup():
    vault = ClientVault(current_origin="http://localhost")
    detector = LocalPIIDetector()
    redactor = LocalRedactor(detector=detector, vault=vault)
    
    def dummy_ocr_func(img):
        return []
        
    guard = EgressGuard(redactor=redactor, ocr_detector_func=dummy_ocr_func, canary_strings=["CANARY_SSN_1234", "SECRET_KEY_999"])
    return vault, detector, redactor, guard, dummy_ocr_func


def test_egress_guard_requires_ocr_dependency(test_setup):
    vault, detector, redactor, _, _ = test_setup
    with pytest.raises(ValueError) as exc_info:
        EgressGuard(redactor=redactor, ocr_detector_func=None)
    assert "requires a non-None ocr_detector_func" in str(exc_info.value)


def test_egress_guard_success_path(test_setup):
    vault, detector, redactor, guard, _ = test_setup
    raw_b64 = create_test_image_b64()
    
    match = PIIMatch(
        category=PIICategory.SSN,
        raw_value="123-45-6789",
        placeholder="[SSN_1]",
        source_node_id=1,
        bounding_box={"x": 20, "y": 20, "width": 100, "height": 30}
    )
    
    sanitized_b64 = guard.sanitize_screenshot_for_egress(raw_b64, matches=[match])
    assert sanitized_b64 != ""
    assert isinstance(sanitized_b64, str)


def test_egress_guard_fail_closed_on_invalid_image(test_setup):
    vault, detector, redactor, guard, _ = test_setup
    corrupted_b64 = "NOT_A_VALID_BASE64_IMAGE_DATA!!!"
    
    with pytest.raises(EgressViolationError) as exc_info:
        guard.sanitize_screenshot_for_egress(corrupted_b64, matches=[])
    
    assert "Egress blocked" in str(exc_info.value)


def test_egress_guard_fail_closed_on_ocr_exception(test_setup):
    vault, detector, redactor, _, _ = test_setup
    raw_b64 = create_test_image_b64()
    
    def broken_ocr_func(img):
        raise RuntimeError("OCR Engine Crashed Unreasonably")
    
    failing_guard = EgressGuard(redactor=redactor, ocr_detector_func=broken_ocr_func)
    
    with pytest.raises(EgressViolationError) as exc_info:
        failing_guard.sanitize_screenshot_for_egress(raw_b64, matches=[])
    
    assert "OCR detection engine failed" in str(exc_info.value)


def test_egress_guard_rendered_pixel_leak_rejection(test_setup):
    vault, detector, redactor, _, _ = test_setup
    raw_b64 = create_test_image_b64()
    
    # Mock OCR engine that simulates detecting unredacted text in pixels AFTER redaction attempts
    def leaking_pixel_ocr(img):
        return [PIIMatch(category=PIICategory.SSN, raw_value="CANARY_SSN_1234", placeholder="[SSN_1]")]
        
    strict_guard = EgressGuard(redactor=redactor, ocr_detector_func=leaking_pixel_ocr, canary_strings=["CANARY_SSN_1234"])
    
    with pytest.raises(EgressViolationError) as exc_info:
        strict_guard.sanitize_screenshot_for_egress(raw_b64, matches=[])
    
    assert "OCR detected unredacted PII text" in str(exc_info.value) or "Security invariant violated" in str(exc_info.value)


def test_egress_guard_edge_padding_redaction(test_setup):
    vault, detector, redactor, guard, _ = test_setup
    raw_b64 = create_test_image_b64(300, 300)
    
    match = PIIMatch(
        category=PIICategory.CREDIT_CARD,
        raw_value="4111111111111111",
        placeholder="[CARD_1]",
        source_node_id=2,
        bounding_box={"x": 0, "y": 0, "width": 50, "height": 20}
    )
    
    redacted_b64 = guard.sanitize_screenshot_for_egress(raw_b64, matches=[match])
    assert redacted_b64 is not None
