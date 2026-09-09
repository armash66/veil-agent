"""
Unit tests for WebVeil Model Context Protocol (MCP) Foundation.
Verifies tool discovery, invocation, security enforcement, and privacy isolation.
"""

import unittest
from unittest.mock import MagicMock

from webveil.core.models.schema import DOMNode, ActionType
from webveil.core.vault.client_vault import ClientVault
from webveil.mcp.server import WebVeilMCPServer
from webveil.mcp.client import WebVeilMCPClient
from webveil.mcp.schema import WEBVEIL_MCP_TOOLS
from webveil.security.firewall.action_firewall import ActionFirewall


class TestMCPFoundation(unittest.TestCase):

    def setUp(self):
        self.vault = ClientVault()
        self.mock_browser = MagicMock()
        self.mock_browser.scroll_page.return_value = True
        self.mock_browser.press_key.return_value = True
        self.mock_browser.click_element.return_value = True

        self.firewall = ActionFirewall(vault=self.vault, browser=self.mock_browser)
        self.server = WebVeilMCPServer(vault=self.vault, browser=self.mock_browser, firewall=self.firewall)
        self.client = WebVeilMCPClient(self.server)

    def test_mcp_initialize_and_tool_discovery(self):
        """Verify MCP handshake and tool catalog exposure."""
        init_res = self.client.initialize()
        self.assertEqual(init_res.get("protocolVersion"), "2024-11-05")
        self.assertEqual(init_res.get("serverInfo", {}).get("name"), "webveil-mcp-server")

        tools = self.client.list_tools()
        self.assertEqual(len(tools), len(WEBVEIL_MCP_TOOLS))
        tool_names = [t["name"] for t in tools]
        self.assertIn("webveil_observe_page", tool_names)
        self.assertIn("webveil_navigate", tool_names)
        self.assertIn("webveil_interact", tool_names)
        self.assertIn("webveil_vault_store", tool_names)
        self.assertIn("webveil_verify_state", tool_names)

    def test_vault_store_tool_preserves_confidentiality(self):
        """Verify webveil_vault_store returns synthetic token without leaking raw secret."""
        raw_password = "SuperSecretPassword123!"
        res = self.client.call_tool("webveil_vault_store", {"secret_value": raw_password, "label": "password"})

        self.assertFalse(res.is_error)
        text_content = res.content[0]["text"]
        # Raw secret must NEVER appear in tool result
        self.assertNotIn(raw_password, text_content)
        self.assertIn("{{VAULT_TOKEN_", text_content)

        # Confirm value is in vault
        token = res.content[0].get("meta", {}).get("token")
        self.assertIsNotNone(token)
        self.assertEqual(self.vault.get_secret_unverified(token), raw_password)

    def test_observe_page_sanitizes_pii(self):
        """Verify webveil_observe_page outputs active nodes and enforces canary egress guard."""
        nodes = [
            DOMNode(node_id=1, tag_name="h1", text_content="Account Dashboard", is_interactive=False, is_visible=True),
            DOMNode(node_id=2, tag_name="button", text_content="Transfer Funds", is_interactive=True, is_visible=True),
        ]
        self.server.set_cached_state(nodes, current_url="https://bank.example.com/home")

        res = self.client.call_tool("webveil_observe_page", {"max_nodes": 10})
        self.assertFalse(res.is_error)
        text = res.content[0]["text"]
        self.assertIn("https://bank.example.com/home", text)
        self.assertIn("Account Dashboard", text)
        self.assertIn("Transfer Funds", text)

    def test_navigate_and_interact_through_firewall(self):
        """Verify tool calls dispatch to browser safely."""
        nodes = [
            DOMNode(node_id=10, tag_name="button", text_content="Submit", is_interactive=True, is_visible=True),
        ]
        self.server.set_cached_state(nodes, current_url="https://app.example.com")

        # Navigate
        nav_res = self.client.call_tool("webveil_navigate", {"url": "https://app.example.com/next"})
        self.assertFalse(nav_res.is_error)
        self.mock_browser.navigate.assert_called_with("https://app.example.com/next")

        # Interact click
        click_res = self.client.call_tool("webveil_interact", {"action": "click", "node_id": 10})
        self.assertFalse(click_res.is_error)
        self.mock_browser.click_element.assert_called_with(10)

    def test_verify_state_tool(self):
        """Verify webveil_verify_state asserts URL and content match."""
        nodes = [
            DOMNode(node_id=1, tag_name="div", text_content="Payment Success! Reference #9876", is_interactive=False, is_visible=True),
        ]
        self.server.set_cached_state(nodes, current_url="https://checkout.example.com/success")

        # Passing verification
        pass_res = self.client.call_tool("webveil_verify_state", {
            "expected_url_contains": "checkout.example.com/success",
            "expected_text_visible": "Payment Success"
        })
        self.assertFalse(pass_res.is_error)
        self.assertIn("PASSED", pass_res.content[0]["text"])

        # Failing verification
        fail_res = self.client.call_tool("webveil_verify_state", {
            "expected_text_visible": "Error 404"
        })
        self.assertTrue(fail_res.is_error)
        self.assertIn("Text not visible", fail_res.content[0]["text"])

    def test_security_violation_returns_error_result(self):
        """Verify adversarial actions return structured error rather than crashing."""
        # Target stale node that doesn't exist
        res = self.client.call_tool("webveil_interact", {"action": "click", "node_id": 9999})
        self.assertTrue(res.is_error)
        self.assertIn("Security Policy Violation", res.content[0]["text"])


if __name__ == "__main__":
    unittest.main()
