"""
URL & Error Sanitization Utilities.
Prevents PII leakage in URLs, query strings, exception messages, and tracebacks.
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from webveil.core.privacy.pii_detector import LocalPIIDetector


class URLErrorSanitizer:
    """
    Sanitizes URLs and exception strings to strip embedded PII.
    """

    def __init__(self, detector: LocalPIIDetector):
        self.detector = detector

    def sanitize_url(self, raw_url: str) -> str:
        """
        Strips PII from query string parameters while keeping URL structure intact.
        """
        if not raw_url:
            return ""

        parsed = urlparse(raw_url)
        if not parsed.query:
            return raw_url

        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sanitized_params = {}

        for key, values in query_params.items():
            key_lower = key.lower()
            sanitized_vals = []
            for v in values:
                if any(kw in key_lower for kw in ["email", "mail", "phone", "aadhaar", "pass", "card", "secret", "user"]):
                    sanitized_vals.append(f"[{key.upper()}_REDACTED]")
                else:
                    # Check value using regex
                    if self.detector.EMAIL_REGEX.search(v):
                        sanitized_vals.append("[EMAIL_REDACTED]")
                    elif self.detector.PHONE_REGEX.search(v):
                        sanitized_vals.append("[PHONE_REDACTED]")
                    elif self.detector.AADHAAR_REGEX.search(v):
                        sanitized_vals.append("[AADHAAR_REDACTED]")
                    elif self.detector.CANARY_REGEX.search(v):
                        sanitized_vals.append("[CANARY_REDACTED]")
                    else:
                        sanitized_vals.append(v)

            sanitized_params[key] = sanitized_vals

        new_query = urlencode(sanitized_params, doseq=True)
        sanitized_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        return sanitized_url

    def sanitize_error(self, error_str: str) -> str:
        """
        Strips PII patterns and synthetic canaries from error stack traces.
        """
        if not error_str:
            return ""

        clean = error_str
        clean = self.detector.EMAIL_REGEX.sub("[EMAIL_REDACTED]", clean)
        clean = self.detector.PHONE_REGEX.sub("[PHONE_REDACTED]", clean)
        clean = self.detector.AADHAAR_REGEX.sub("[AADHAAR_REDACTED]", clean)
        clean = self.detector.CANARY_REGEX.sub("[CANARY_REDACTED]", clean)
        clean = self.detector.CREDIT_CARD_REGEX.sub("[CARD_REDACTED]", clean)
        return clean
