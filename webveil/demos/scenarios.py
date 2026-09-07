"""
Predefined Demo Scenarios.
Each scenario defines a task, URL, and optional setup function.
"""

import threading
import time


def get_scenario(name: str) -> dict:
    """Get a predefined demo scenario by name."""
    scenarios = {
        "kyc": _kyc_scenario(),
        "web": _web_scenario(),
        "visual": _visual_scenario(),
    }
    if name not in scenarios:
        raise ValueError(f"Unknown scenario: {name}. Available: {list(scenarios.keys())}")
    return scenarios[name]


def _kyc_scenario() -> dict:
    """
    Demo A — Privacy: KYC form with canary PII data.
    Proves: PII detection → local vault → sanitized reasoning → local restoration.
    """
    def setup():
        from test_page.test_server import run_server, PORT
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(1.0)

    return {
        "name": "KYC Privacy Demo",
        "task": "Fill and submit this KYC verification form.",
        "url": "http://127.0.0.1:8080/index.html",
        "setup": setup,
        "description": (
            "Privacy demonstration: Agent fills a KYC form containing "
            "email, phone, Aadhaar, and password fields. All PII is detected, "
            "replaced with placeholders for remote reasoning, and restored "
            "locally by the vault during execution. Zero raw PII leaves the device."
        ),
    }


def _web_scenario() -> dict:
    """
    Demo B — General Agent: Web navigation on a real website.
    Proves: genuine browser agent capability on unseen pages.
    """
    return {
        "name": "Web Navigation Demo",
        "task": "Go to the Wikipedia page for ISRO and find when ISRO was founded.",
        "url": "https://en.wikipedia.org/wiki/Indian_Space_Research_Organisation",
        "setup": None,
        "description": (
            "General agent demonstration: Agent navigates a real website, "
            "reads content, and extracts information. No hardcoded behavior — "
            "the agent uses LLM reasoning to understand page structure."
        ),
    }


def _visual_scenario() -> dict:
    """
    Demo C — Visual Agent: Canvas-based interaction.
    Proves: on-device visual perception where DOM is insufficient.
    """
    def setup():
        from test_page.test_server import run_server, PORT
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(1.0)

    return {
        "name": "Visual Perception Demo",
        "task": (
            "Look at the canvas display. Read the text shown visually on the canvas. "
            "Then click the button that matches the instruction displayed on the canvas."
        ),
        "url": "http://127.0.0.1:8080/canvas_challenge.html",
        "setup": setup,
        "description": (
            "Visual perception demonstration: A canvas element displays text "
            "and interactive regions that have NO DOM representation. "
            "The agent must use local OCR to 'see' the canvas, understand "
            "the visual instructions, and act accordingly."
        ),
    }
