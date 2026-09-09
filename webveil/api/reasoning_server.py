"""
WebVeil Thin Reasoning Server.

This is a MINIMAL FastAPI endpoint that:
  - Accepts POST /api/reason with {task, sanitized_dom, action_history}
  - Calls ONLY the ReasoningProvider (Gemini/OpenAI/mock) to get an action plan
  - Returns {thought, actions}

It does NOT:
  - Launch Playwright or any browser
  - Do PII detection (that's the content script's job)
  - Do vault management (that's the content script's job)
  - Do DOM pruning (that's the content script's job)
  - Do redaction (that's the content script's job)
  - Do egress audit (content script handles this before sending)

This server receives ONLY pre-sanitized, pre-redacted data from the extension.

Usage:
  python -m webveil.api.reasoning_server
  # Starts on http://127.0.0.1:8000
"""

import json
import logging
import asyncio
import uvicorn
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from webveil.config import config
from webveil.reasoning.provider import create_provider
from webveil.core.models.schema import (
    ActionPlan, ActionType, BrowserAction,
    SanitizedWorldModel, DOMNode as CoreDOMNode,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebVeilReasoningServer")

# ── App ──
app = FastAPI(
    title="WebVeil Reasoning Server",
    description="Thin reasoning-only endpoint for the WebVeil extension. Receives sanitized DOM, returns action plans.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Extension origin
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ── Request / Response Models ──
class DOMNode(BaseModel):
    node_id: int
    tag_name: str
    element_type: str = ""
    text_content: str = ""
    is_interactive: bool = False
    bounding_box: Optional[Dict[str, int]] = None

class ReasonRequest(BaseModel):
    task: str
    sanitized_dom: Optional[List[DOMNode]] = None
    dom: Optional[List[DOMNode]] = None
    action_history: List[Dict[str, Any]] = []
    url: str = ""
    title: str = ""
    redaction_summary: Optional[Dict[str, Any]] = None

class ActionResponse(BaseModel):
    action: str
    node_id: Optional[int] = None
    text: Optional[str] = None
    thought: str = ""
    rationale: str = ""

class ReasonResponse(BaseModel):
    thought: str
    actions: List[ActionResponse]

# ── Provider (initialized once) ──
_provider = None

def get_provider():
    global _provider
    if _provider is None:
        provider_name = config.provider
        warnings = config.validate()
        for w in warnings:
            logger.warning(w)
        provider_name = config.provider  # May have fallen back

        try:
            kwargs = {}
            if provider_name == "gemini":
                kwargs = {"api_key": config.gemini_api_key, "model": config.gemini_model}
            elif provider_name == "openai":
                kwargs = {"api_key": config.openai_api_key, "model": config.openai_model}
            _provider = create_provider(provider_name, **kwargs)
            logger.info(f"Reasoning provider initialized: {provider_name}")
        except Exception as e:
            logger.warning(f"Provider '{provider_name}' init failed: {e}. Using mock.")
            _provider = create_provider("mock")

    return _provider

# ── Routes ──
@app.get("/api/health")
@app.get("/health")
async def health():
    provider = get_provider()
    return {
        "status": "ok",
        "provider": provider.provider_name,
        "description": "Thin reasoning-only server. No Playwright, no vault, no PII detection.",
    }

@app.post("/api/reason", response_model=ReasonResponse)
async def reason(request: ReasonRequest):
    """
    Accept sanitized (pre-redacted) DOM + task, return action plan.
    This endpoint does NOT inspect, detect, or redact PII — that's the extension's job.
    """
    provider = get_provider()
    nodes = request.sanitized_dom or request.dom or []
    logger.info(f"[Reason] Task: '{request.task}' | DOM nodes: {len(nodes)} | URL: {request.url}")

    # Build formatted DOM text for prompt
    formatted_dom = _format_dom_for_prompt(nodes)

    # Convert request nodes to core schema DOMNode
    core_nodes = [
        CoreDOMNode(
            node_id=n.node_id,
            tag_name=n.tag_name,
            element_type=n.element_type,
            text_content=n.text_content,
            is_interactive=n.is_interactive,
            bounding_box=n.bounding_box,
        )
        for n in nodes
    ]

    redacted_count = 0
    if request.redaction_summary and isinstance(request.redaction_summary, dict):
        redacted_count = request.redaction_summary.get("total_redacted", 0)

    # Build SanitizedWorldModel directly for the provider
    sanitized_model = SanitizedWorldModel(
        url=request.url,
        sanitized_url=request.url,
        title=request.title,
        sanitized_dom=core_nodes,
        formatted_dom=formatted_dom,
        a11y_summary="",
        ocr_summary="",
        redacted_screenshot_b64=None,
        detected_pii_count=redacted_count,
        pii_categories_found=[],
    )

    # Build action history
    from webveil.core.models.schema import ActionResult
    history = []

    try:
        plan: ActionPlan = await asyncio.to_thread(
            provider.reason,
            task=request.task,
            world_model=sanitized_model,
            action_history=history,
            error_context=None,
        )

        return ReasonResponse(
            thought=plan.thought or "",
            actions=[
                ActionResponse(
                    action=a.action.value,
                    node_id=a.node_id,
                    text=a.text,
                    thought=a.thought or "",
                    rationale=a.thought or f"I'll execute {a.action.value} on node #{a.node_id if a.node_id is not None else 'N/A'}",
                )
                for a in plan.actions
            ],
        )
    except Exception as e:
        logger.error(f"[Reason] Provider error: {e}")
        return ReasonResponse(
            thought=f"Reasoning failed: {str(e)[:200]}",
            actions=[ActionResponse(action="WAIT", thought="Reasoning error, please retry")],
        )


def _format_dom_for_prompt(nodes: List[DOMNode]) -> str:
    """Format sanitized DOM nodes into a text representation for LLM prompt."""
    lines = []
    for node in nodes:
        parts = [f"[{node.node_id}]", f"<{node.tag_name}>"]
        if node.element_type:
            parts.append(f'type="{node.element_type}"')
        if node.text_content:
            parts.append(f'"{node.text_content[:100]}"')
        if node.is_interactive:
            parts.append("[interactive]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


# ── Entry point ──
def main():
    logger.info("Starting WebVeil Thin Reasoning Server on http://127.0.0.1:8000")
    logger.info("This server does ONLY reasoning. No Playwright, no vault, no PII detection.")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
