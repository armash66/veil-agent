"""
WebVeil Model Context Protocol (MCP) Server.
Implements the JSON-RPC 2.0 MCP standard, exposing privacy-preserving browser automation
and vault operations to MCP-compliant reasoning engines and IDEs.
"""

import json
import logging
from typing import Dict, Any, Optional, List

from webveil.core.models.schema import BrowserAction, ActionType, DOMNode, SanitizedWorldModel
from webveil.core.vault.client_vault import ClientVault
from webveil.core.privacy.pii_detector import LocalPIIDetector
from webveil.security.firewall.action_firewall import ActionFirewall, ActionSecurityViolation
from webveil.security.egress_guard import EgressViolationError
from webveil.mcp.schema import WEBVEIL_MCP_TOOLS, MCPToolCallResult

logger = logging.getLogger("WebVeilMCP.Server")


class WebVeilMCPServer:
    """
    Lightweight, secure MCP Server for WebVeil.
    All incoming tool calls pass through privacy and firewall choke points.
    """

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "webveil-mcp-server"
    SERVER_VERSION = "1.0.0"

    def __init__(
        self,
        vault: Optional[ClientVault] = None,
        browser: Optional[Any] = None,
        firewall: Optional[ActionFirewall] = None,
        pii_detector: Optional[LocalPIIDetector] = None,
    ):
        self.vault = vault or ClientVault()
        self.browser = browser
        self.firewall = firewall or ActionFirewall(vault=self.vault, browser=self.browser)
        self.pii_detector = pii_detector or LocalPIIDetector()

        # Cache of latest active DOM nodes for interact calls
        self._cached_nodes: List[DOMNode] = []
        self._current_url: str = "about:blank"

    def set_cached_state(self, nodes: List[DOMNode], current_url: str = "about:blank"):
        """Update active page DOM cache for targeted interactions."""
        self._cached_nodes = nodes
        self._current_url = current_url

    def handle_request_json(self, raw_json_str: str) -> str:
        """Parse and execute a JSON-RPC 2.0 MCP request string."""
        try:
            req = json.loads(raw_json_str)
        except json.JSONDecodeError as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            })

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        response = self.dispatch(method, params, req_id)
        return json.dumps(response)

    def dispatch(self, method: str, params: Dict[str, Any], req_id: Any) -> Dict[str, Any]:
        """Dispatch JSON-RPC method."""
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "serverInfo": {"name": self.SERVER_NAME, "version": self.SERVER_VERSION},
                    "capabilities": {"tools": {}},
                }
            }

        elif method == "notifications/initialized":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        }
                        for t in WEBVEIL_MCP_TOOLS
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            call_result = self.execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": call_result.content,
                    "isError": call_result.is_error,
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Route tool invocation with strict privacy and security boundaries."""
        try:
            if tool_name == "webveil_observe_page":
                return self._tool_observe_page(arguments)

            elif tool_name == "webveil_navigate":
                return self._tool_navigate(arguments)

            elif tool_name == "webveil_interact":
                return self._tool_interact(arguments)

            elif tool_name == "webveil_vault_store":
                return self._tool_vault_store(arguments)

            elif tool_name == "webveil_verify_state":
                return self._tool_verify_state(arguments)

            else:
                return MCPToolCallResult.error(f"Unknown tool: {tool_name}")

        except (ActionSecurityViolation, EgressViolationError) as sec_err:
            logger.critical(f"[MCP Security Block] Blocked execution: {sec_err}")
            return MCPToolCallResult.error(f"Security Policy Violation: {sec_err}")
        except Exception as e:
            logger.exception(f"[MCP Execution Error] Tool {tool_name} failed: {e}")
            return MCPToolCallResult.error(str(e))

    def _tool_observe_page(self, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Inspect and return sanitized page state."""
        max_nodes = arguments.get("max_nodes", 50)
        
        # Build sanitized summary
        active_nodes = self._cached_nodes[:max_nodes]
        nodes_summary = [
            f"Node [{n.node_id}] <{n.tag_name}> '{n.text_content[:40]}'"
            for n in active_nodes if n.is_interactive or n.text_content
        ]
        text_out = f"URL: {self._current_url}\nActive Nodes ({len(active_nodes)}):\n" + "\n".join(nodes_summary)
        
        # Verify no raw PII escapes in output
        matches = self.pii_detector.scan_text(text_out)
        if matches:
            logger.critical(f"[MCP OBSERVATION BLOCK] Detected {len(matches)} unredacted PII secrets in observation")
            raise EgressViolationError(f"PII detected in output: {matches[0].category.value}")

        return MCPToolCallResult.success(text_out)

    def _tool_navigate(self, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Navigate to URL through Action Firewall."""
        url = arguments.get("url")
        if not url:
            return MCPToolCallResult.error("Missing required parameter 'url'")

        action = BrowserAction(action=ActionType.NAVIGATE, url=url)
        self.firewall.execute_validated_action(action, self._cached_nodes, self._current_url)
        self._current_url = url
        return MCPToolCallResult.success(f"Navigated successfully to {url}")

    def _tool_interact(self, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Execute interaction through Action Firewall."""
        act_str = arguments.get("action", "").upper()
        if act_str not in ActionType.__members__:
            return MCPToolCallResult.error(f"Invalid action type: {act_str}")

        action_type = ActionType[act_str]
        action = BrowserAction(
            action=action_type,
            node_id=arguments.get("node_id"),
            text=arguments.get("text"),
            key=arguments.get("key"),
            direction=arguments.get("direction"),
            amount=arguments.get("amount"),
        )

        success = self.firewall.execute_validated_action(action, self._cached_nodes, self._current_url)
        return MCPToolCallResult.success(f"Action {act_str} executed successfully: {success}")

    def _tool_vault_store(self, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Store secret in client vault and return opaque token."""
        secret = arguments.get("secret_value")
        label = arguments.get("label", "secret")
        if not secret:
            return MCPToolCallResult.error("Missing required parameter 'secret_value'")

        token = self.vault.store_secret(secret, label=label)
        return MCPToolCallResult.success(
            f"Stored securely in local vault. Use token '{token}' in subsequent interaction steps.",
            extra_meta={"token": token}
        )

    def _tool_verify_state(self, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Verify URL or visible text."""
        url_substr = arguments.get("expected_url_contains")
        text_substr = arguments.get("expected_text_visible")

        checks = []
        if url_substr:
            matched = url_substr.lower() in self._current_url.lower()
            checks.append(f"URL match '{url_substr}': {'PASSED' if matched else 'FAILED'}")
            if not matched:
                return MCPToolCallResult.error(f"URL mismatch: '{url_substr}' not found in '{self._current_url}'")

        if text_substr:
            matched = any(text_substr.lower() in n.text_content.lower() for n in self._cached_nodes)
            checks.append(f"Text match '{text_substr}': {'PASSED' if matched else 'FAILED'}")
            if not matched:
                return MCPToolCallResult.error(f"Text not visible: '{text_substr}'")

        return MCPToolCallResult.success("Verification passed: " + "; ".join(checks))
