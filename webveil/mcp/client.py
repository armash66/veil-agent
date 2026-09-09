"""
WebVeil MCP Client.
Programmatic client for interacting with a WebVeil MCP server instance.
"""

import json
from typing import Dict, Any, List, Optional
from webveil.mcp.server import WebVeilMCPServer
from webveil.mcp.schema import MCPToolCallResult


class WebVeilMCPClient:
    """
    Client for testing or delegating tasks to a local WebVeilMCPServer.
    """

    def __init__(self, server: WebVeilMCPServer):
        self.server = server
        self._request_id = 1

    def _next_id(self) -> int:
        req_id = self._request_id
        self._request_id += 1
        return req_id

    def initialize(self) -> Dict[str, Any]:
        """Perform MCP handshake."""
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {"clientInfo": {"name": "test-client", "version": "1.0.0"}},
        }
        res_json = self.server.handle_request_json(json.dumps(msg))
        return json.loads(res_json).get("result", {})

    def list_tools(self) -> List[Dict[str, Any]]:
        """Query available tools from server."""
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        }
        res_json = self.server.handle_request_json(json.dumps(msg))
        return json.loads(res_json).get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> MCPToolCallResult:
        """Invoke an MCP tool on the server."""
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        res_json = self.server.handle_request_json(json.dumps(msg))
        res_data = json.loads(res_json).get("result", {})
        return MCPToolCallResult(
            content=res_data.get("content", []),
            is_error=res_data.get("isError", False),
        )
