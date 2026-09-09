"""
Model Context Protocol (MCP) Schemas for WebVeil.
Implements JSON-RPC 2.0 and MCP specification structures for tool registration and invocation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPToolCallRequest:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolCallResult:
    content: List[Dict[str, Any]] = field(default_factory=list)
    is_error: bool = False

    @classmethod
    def success(cls, text: str, extra_meta: Optional[Dict[str, Any]] = None) -> "MCPToolCallResult":
        payload = {"type": "text", "text": text}
        if extra_meta:
            payload["meta"] = extra_meta
        return cls(content=[payload], is_error=False)

    @classmethod
    def error(cls, error_message: str) -> "MCPToolCallResult":
        return cls(content=[{"type": "text", "text": f"Error: {error_message}"}], is_error=True)


# Standard WebVeil MCP Tool Definitions
WEBVEIL_MCP_TOOLS: List[MCPTool] = [
    MCPTool(
        name="webveil_observe_page",
        description="Inspect active webpage. Redacts all PII and returns sanitized DOM, accessibility hierarchy, and perception summary.",
        input_schema={
            "type": "object",
            "properties": {
                "max_nodes": {"type": "integer", "description": "Maximum interactive DOM nodes to return", "default": 50},
            },
            "required": [],
        },
    ),
    MCPTool(
        name="webveil_navigate",
        description="Navigate the browser to a destination URL through the WebVeil Action Firewall.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target HTTP or HTTPS URL to navigate to"},
            },
            "required": ["url"],
        },
    ),
    MCPTool(
        name="webveil_interact",
        description="Execute a validated interaction (click, type, scroll, keypress) through the Action Firewall and Visual Grounder.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "scroll", "keypress"], "description": "Action type"},
                "node_id": {"type": "integer", "description": "Target DOM node ID"},
                "text": {"type": "string", "description": "Text to type (use {{VAULT_TOKEN_*}} for protected secrets)"},
                "key": {"type": "string", "description": "Keyboard key name (e.g. Enter)"},
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction"},
                "amount": {"type": "integer", "description": "Scroll pixel distance"},
            },
            "required": ["action"],
        },
    ),
    MCPTool(
        name="webveil_vault_store",
        description="Store a sensitive user credential (password, Aadhaar, PAN, API key) directly into the local Client Vault, returning a synthetic opaque token. Zero secret exposure.",
        input_schema={
            "type": "object",
            "properties": {
                "secret_value": {"type": "string", "description": "Raw sensitive credential to protect"},
                "label": {"type": "string", "description": "Optional human-readable label (e.g. password, aadhaar)"},
            },
            "required": ["secret_value"],
        },
    ),
    MCPTool(
        name="webveil_verify_state",
        description="Verify current browser page against expected conditions (URL match, DOM presence, success indicators).",
        input_schema={
            "type": "object",
            "properties": {
                "expected_url_contains": {"type": "string", "description": "Substring expected in current page URL"},
                "expected_text_visible": {"type": "string", "description": "Text substring expected to be visible on page"},
            },
            "required": [],
        },
    ),
]
