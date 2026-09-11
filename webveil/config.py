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
        self.provider: str = os.getenv("REASONING_PROVIDER") or os.getenv("WEBVEIL_PROVIDER", "cascade")
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openrouter_model: str = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")

        # Agent settings
        self.max_steps: int = int(os.getenv("WEBVEIL_MAX_STEPS", "20"))
        self.max_actions_per_plan: int = int(os.getenv("WEBVEIL_MAX_ACTIONS_PER_PLAN", "15"))
        self.headless: bool = os.getenv("WEBVEIL_HEADLESS", "false").lower() == "true"

        # Dashboard
        self.dashboard_port: int = int(os.getenv("WEBVEIL_DASHBOARD_PORT", "9090"))

        # OCR
        self.ocr_enabled: bool = os.getenv("WEBVEIL_OCR_ENABLED", "true").lower() == "true"

    def validate(self) -> list[str]:
        """Returns list of warnings about configuration issues."""
        warnings = []
        if self.provider == "cascade":
            # Cascade gracefully handles missing keys across its 3 tiers
            if not self.openrouter_api_key and not self.gemini_api_key:
                warnings.append("No cloud fallback API keys set (OPENROUTER_API_KEY or GEMINI_API_KEY). Cascade will run local Ollama with mock safety net.")
        elif self.provider == "gemini" and not self.gemini_api_key:
            if self.openrouter_api_key:
                warnings.append("GEMINI_API_KEY is not set; falling back to openrouter provider.")
                self.provider = "openrouter"
            else:
                warnings.append("GEMINI_API_KEY is not set; falling back to mock provider.")
                self.provider = "mock"
        elif self.provider == "openrouter" and not self.openrouter_api_key:
            if self.gemini_api_key:
                warnings.append("OPENROUTER_API_KEY is not set; falling back to gemini provider.")
                self.provider = "gemini"
            else:
                warnings.append("OPENROUTER_API_KEY is not set; falling back to mock provider.")
                self.provider = "mock"
        elif self.provider == "openai" and not self.openai_api_key:
            warnings.append("OPENAI_API_KEY is not set. Falling back to mock provider.")
            self.provider = "mock"
        return warnings

    def reload(self):
        """Reload configuration from .env file and environment variables."""
        try:
            from dotenv import load_dotenv
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                load_dotenv(env_file, override=True)
        except Exception:
            pass
        self.__init__()


# Global singleton
config = WebVeilConfig()
