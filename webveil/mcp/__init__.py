"""
WebVeil Model Context Protocol (MCP) Foundation.
"""

from webveil.mcp.schema import MCPTool, MCPToolCallRequest, MCPToolCallResult, WEBVEIL_MCP_TOOLS
from webveil.mcp.server import WebVeilMCPServer
from webveil.mcp.client import WebVeilMCPClient

__all__ = [
    "MCPTool",
    "MCPToolCallRequest",
    "MCPToolCallResult",
    "WEBVEIL_MCP_TOOLS",
    "WebVeilMCPServer",
    "WebVeilMCPClient",
]
