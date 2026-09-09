"""
Unit and integration tests for WebVeil local instruction-file system,
privacy pipeline egress filtering, and Agent Activity card UX invariants.
"""

import os
import unittest
from fastapi.testclient import TestClient
from webveil.core.models.schema import (
    DOMNode,
    SanitizedWorldModel,
    TaskRepresentation,
)
from webveil.core.context.manager import LocalContextManager, SelectedContextPayload
from webveil.api.reasoning_server import app, ReasonRequest
from webveil.reasoning.provider import build_reasoning_context, create_provider


class TestInstructionSystem(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.context_manager = LocalContextManager(max_selected_elements=5)

    def test_schema_supports_instruction_context(self):
        """Verify schema models accept instruction_context."""
        swm = SanitizedWorldModel(
            url="https://test.local",
            sanitized_url="https://test.local",
            title="Test Page",
            sanitized_dom=[],
            formatted_dom="",
            a11y_summary="",
            ocr_summary="",
            instruction_context="Rule 1: Never disclose internal IDs.",
        )
        self.assertEqual(swm.instruction_context, "Rule 1: Never disclose internal IDs.")

        payload = SelectedContextPayload(
            task="Perform search",
            active_goal="Search items",
            url="https://test.local",
            page_title="Test Page",
            selected_dom_nodes=[],
            formatted_dom="",
            a11y_summary="",
            ocr_summary="",
            visual_summary="",
            recent_failures=[],
            provenance_map={"task": "user_instruction"},
            compression_stats=None,
            instruction_context="Rule 1: Never disclose internal IDs.",
        )
        self.assertEqual(payload.instruction_context, "Rule 1: Never disclose internal IDs.")

    def test_context_manager_attaches_instruction_context_and_provenance(self):
        """Verify LocalContextManager passes instruction context with provenance."""
        nodes = [
            DOMNode(node_id=1, tag_name="button", text_content="Submit", is_visible=True, is_interactive=True)
        ]
        world_model = SanitizedWorldModel(
            url="https://test.local",
            sanitized_url="https://test.local",
            title="Test Page",
            sanitized_dom=nodes,
            formatted_dom="",
            a11y_summary="",
            ocr_summary="",
        )

        custom_instructions = "Constraint: Only click submit if form is valid."
        payload = self.context_manager.select_context(
            task="Submit form",
            world_model=world_model,
            instruction_context=custom_instructions,
        )

        self.assertEqual(payload.instruction_context, custom_instructions)
        self.assertEqual(payload.provenance_map.get("instructions"), "local_instruction_file")

    def test_reasoning_context_builder_includes_instructions(self):
        """Verify build_reasoning_context includes instructions in provider prompt."""
        world_model = SanitizedWorldModel(
            url="https://test.local",
            sanitized_url="https://test.local",
            title="Checkout Page",
            sanitized_dom=[],
            formatted_dom="[1] <button>Pay</button>",
            a11y_summary="",
            ocr_summary="",
            instruction_context="CONSTRAINTS:\n- Do not confirm payment automatically\n- Ask user first",
        )

        prompt = build_reasoning_context(
            task="Pay now",
            world_model=world_model,
            action_history=[],
        )

        self.assertIn("USER INSTRUCTIONS & CONSTRAINTS (from local instruction file):", prompt)
        self.assertIn("Do not confirm payment automatically", prompt)

    def test_reasoning_server_api_with_instruction_context(self):
        """Verify /api/reason endpoint processes instruction_context without error."""
        payload = {
            "task": "summarize page with rules",
            "url": "https://example.com",
            "title": "Example Domain",
            "dom": [
                {
                    "node_id": 1,
                    "tag_name": "h1",
                    "element_type": "text",
                    "text_content": "Example Domain",
                    "is_interactive": False,
                }
            ],
            "provider": "mock",
            "model": "local",
            "instruction_context": "Format summary in 3 bullet points only.",
            "redaction_summary": {
                "total_redacted": 0,
                "tokens": [],
            },
        }

        response = self.client.post("/api/reason", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("thought", data)
        self.assertIn("actions", data)

    def test_sidepanel_html_and_css_ui_invariants(self):
        """
        Verify sidepanel UI adheres to all UX revision requirements:
        1. Instructions selector elements present.
        2. Accepts .md and .txt.
        3. TRANSMITTED metric and old 3-card counters are absent.
        4. Thumbs-up/down feedback row is absent.
        5. Agent Activity card & collapsible What WebVeil saw styles exist.
        """
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../extension"))
        html_path = os.path.join(base_dir, "sidepanel.html")
        css_path = os.path.join(base_dir, "sidepanel.css")
        js_path = os.path.join(base_dir, "sidepanel.js")

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # 1. Instructions selector in HTML
        self.assertIn('id="instructions-btn"', html)
        self.assertIn('id="instructions-dropdown-menu"', html)
        self.assertIn('id="instruction-file-input"', html)
        self.assertIn('accept=".md,.txt"', html)

        # 2. No TRANSMITTED metric or old counters in HTML or user-facing card
        self.assertNotIn('wv-counter-transmitted', html)
        self.assertNotIn('wv-counter-actions', html)
        self.assertNotIn('wv-counters', html)

        # 3. No thumbs-up/down feedback buttons in HTML or newly generated cards
        self.assertNotIn('wv-feedback-row', html)
        self.assertNotIn('wv-feedback-row', js)

        # 4. Agent Activity card styles
        self.assertIn('.wv-activity-card', css)
        self.assertIn('.wv-privacy-status-badge', css)
        self.assertIn('.wv-saw-collapsible', css)
        self.assertIn('.wv-instructions-pill', css)
        self.assertIn('.wv-instructions-menu', css)

        # 5. JS uses buildActivityCard
        self.assertIn('function buildActivityCard', js)
        self.assertIn('sanitizeAndSelectInstructions', js)
        self.assertIn('loadInstructionFiles', js)
        self.assertIn('handleInstructionFileImport', js)


if __name__ == "__main__":
    unittest.main()
