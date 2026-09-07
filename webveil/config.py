"""
WebVeil Configuration.
Loads settings from .env file and environment variables with sensible defaults.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("WebVeilConfig")

# Try to load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded configuration from {env_path}")
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly


class WebVeilConfig:
    """Centralized configuration for all WebVeil subsystems."""

    def __init__(self):
        # Reasoning provider
        self.provider: str = os.getenv("WEBVEIL_PROVIDER", "mock")
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Agent settings
        self.max_steps: int = int(os.getenv("WEBVEIL_MAX_STEPS", "20"))
        self.max_actions_per_plan: int = int(os.getenv("WEBVEIL_MAX_ACTIONS_PER_PLAN", "5"))
        self.headless: bool = os.getenv("WEBVEIL_HEADLESS", "false").lower() == "true"

        # Dashboard
        self.dashboard_port: int = int(os.getenv("WEBVEIL_DASHBOARD_PORT", "9090"))

        # OCR
        self.ocr_enabled: bool = os.getenv("WEBVEIL_OCR_ENABLED", "true").lower() == "true"

    def validate(self) -> list[str]:
        """Returns list of warnings about configuration issues."""
        warnings = []
        if self.provider == "gemini" and not self.gemini_api_key:
            warnings.append("WEBVEIL_PROVIDER=gemini but GEMINI_API_KEY is not set. Falling back to mock provider.")
            self.provider = "mock"
        if self.provider == "openai" and not self.openai_api_key:
            warnings.append("WEBVEIL_PROVIDER=openai but OPENAI_API_KEY is not set. Falling back to mock provider.")
            self.provider = "mock"
        return warnings


# Global singleton
config = WebVeilConfig()
