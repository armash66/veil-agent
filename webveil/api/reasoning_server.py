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
from webveil.core.perception.ocr import OCREngine
from webveil.core.models.schema import (
    ActionPlan, ActionType, BrowserAction,
    SanitizedWorldModel, DOMNode as CoreDOMNode,
)

_ocr_engine = OCREngine(enabled=True)

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
    element_id: str = ""
    element_name: str = ""
    placeholder: str = ""
    value: str = ""
    aria_label: str = ""
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
    provider: Optional[str] = None
    model: Optional[str] = None
    instruction_context: Optional[str] = None
    instructions: Optional[str] = None
    sanitized_screenshot_b64: Optional[str] = None
    visual_telemetry: Optional[Dict[str, Any]] = None
    ocr_summary: Optional[str] = ""
    canvas_images: Optional[List[Dict[str, Any]]] = None

class ActionResponse(BaseModel):
    action: str
    node_id: Optional[int] = None
    text: Optional[str] = None
    url: Optional[str] = None
    key: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[int] = None
    value: Optional[str] = None
    thought: str = ""
    rationale: str = ""

class ReasonResponse(BaseModel):
    thought: str
    actions: List[ActionResponse]
    provider_used: str = "Local (Ollama)"
    tier_used: str = "Local (Ollama)"

# ── Provider Resolution & Caching ──
_provider_cache: Dict[str, Any] = {}

def get_provider(requested_provider: Optional[str] = None, requested_model: Optional[str] = None):
    config.reload()

    req_p = (requested_provider or "").strip().lower()
    req_m = (requested_model or "").strip()

    # Default to cascade if none requested or "cascade" requested
    if not req_p or req_p in ("cascade", "default", "auto", "local-first"):
        cache_key = "cascade"
        if cache_key in _provider_cache:
            return _provider_cache[cache_key]
        provider_inst = create_provider(
            "cascade",
            ollama_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            openrouter_key=config.openrouter_api_key,
            openrouter_model=config.openrouter_model,
            gemini_key=config.gemini_api_key,
            gemini_model=config.gemini_model,
        )
        _provider_cache[cache_key] = provider_inst
        logger.info("[Server] Initialized CascadeReasoningProvider (Ollama -> OpenRouter -> Gemini)")
        return provider_inst

    # Infer provider if not explicit
    if req_m:
        m_lower = req_m.lower()
        if "openrouter" in m_lower or "nemotron" in m_lower:
            req_p = "openrouter"
        elif "gemini" in m_lower:
            req_p = "gemini"
        elif "ollama" in m_lower or "llama" in m_lower:
            req_p = "ollama"
        elif "mock" in m_lower:
            req_p = "mock"

    # Validate provider credentials for individual provider overrides
    if req_p == "ollama":
        model = req_m or config.ollama_model
        api_key = None
    elif req_p == "openrouter":
        if not config.openrouter_api_key:
            logger.warning("[Server] OPENROUTER_API_KEY missing; falling back to mock")
            req_p = "mock"
        model = req_m or config.openrouter_model
        api_key = config.openrouter_api_key
    elif req_p == "gemini":
        if not config.gemini_api_key:
            logger.warning("[Server] GEMINI_API_KEY missing; falling back to openrouter or mock")
            if config.openrouter_api_key:
                req_p = "openrouter"
                model = config.openrouter_model
                api_key = config.openrouter_api_key
            else:
                req_p = "mock"
                model = "mock"
                api_key = None
        else:
            model = req_m or config.gemini_model
            api_key = config.gemini_api_key
    elif req_p == "openai":
        model = req_m or config.openai_model
        api_key = config.openai_api_key
    else:
        req_p = "mock"
        model = "mock"
        api_key = None

    cache_key = f"{req_p}:{model}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    try:
        kwargs = {}
        if req_p == "ollama":
            kwargs = {"base_url": config.ollama_base_url, "model": model}
        elif req_p == "gemini":
            kwargs = {"api_key": api_key, "model": model}
        elif req_p == "openrouter":
            kwargs = {"api_key": api_key, "model": model}
        elif req_p == "openai":
            kwargs = {"api_key": api_key, "model": model}

        provider_inst = create_provider(req_p, **kwargs)
        _provider_cache[cache_key] = provider_inst
        logger.info(f"Reasoning provider initialized: {req_p} (model: {model})")
        return provider_inst
    except Exception as e:
        logger.warning(f"Provider '{req_p}' init failed: {e}. Using mock.")
        return create_provider("mock")

# ── Routes ──
@app.get("/api/health")
@app.get("/health")
async def health():
    provider = get_provider()
    raw_tier = getattr(provider, "active_tier", None) or getattr(provider, "provider_name", "Local (Ollama)")
    active_tier = str(raw_tier) if not hasattr(raw_tier, "_mock_name") else "Local (Ollama)"
    p_name = getattr(provider, "provider_name", "Cascade")
    provider_name = str(p_name) if not hasattr(p_name, "_mock_name") else "Cascade"
    return {
        "status": "ok",
        "provider": provider_name,
        "active_tier": active_tier,
        "description": "Thin reasoning-only server with 3-Tier Escalation Cascade (Ollama -> OpenRouter -> Gemini).",
    }

@app.get("/api/evaluate")
async def evaluate():
    """Run full SIH evaluation suite across the 5 official criteria and return executive scorecard."""
    from webveil.evaluation.sih_evaluator import SIHEvaluationEngine
    engine = SIHEvaluationEngine()
    summary = await asyncio.to_thread(engine.run_full_evaluation)
    res = summary.to_dict()
    res["markdown_report"] = summary.generate_markdown_report()
    return res

@app.post("/api/reason", response_model=ReasonResponse)
async def reason(request: ReasonRequest):
    """
    Accept sanitized (pre-redacted) DOM + task, return action plan.
    This endpoint does NOT inspect, detect, or redact PII — that's the extension's job.
    """
    provider = get_provider(request.provider, request.model)
    nodes = request.sanitized_dom or request.dom or []
    logger.info(f"[Reason] Using {provider.provider_name} | Task: '{request.task}' | DOM nodes: {len(nodes)} | URL: {request.url}")

    # Build formatted DOM text for prompt
    formatted_dom = _format_dom_for_prompt(nodes)

    # Convert request nodes to core schema DOMNode
    core_nodes = [
        CoreDOMNode(
            node_id=n.node_id,
            tag_name=n.tag_name,
            element_type=n.element_type,
            element_id=n.element_id,
            name=n.element_name,
            text_content=n.text_content,
            value=n.value,
            is_interactive=n.is_interactive,
            bounding_box=n.bounding_box,
        )
        for n in nodes
    ]

    redacted_count = 0
    if request.redaction_summary and isinstance(request.redaction_summary, dict):
        redacted_count = request.redaction_summary.get("total_redacted", 0)

    visual_summary = ""
    visual_count = 0
    if request.visual_telemetry and isinstance(request.visual_telemetry, dict):
        visual_count = request.visual_telemetry.get("regions_count", 0)
        backend = request.visual_telemetry.get("backend", "local")
        inf_ms = request.visual_telemetry.get("inference_ms", 0)
        visual_summary = f"Local vision ({backend}): {visual_count} regions ({inf_ms}ms)"
        logger.info(f"[Reason] Visual Telemetry: backend={backend} | latency={inf_ms}ms | regions={visual_count}")

    # Extract OCR from canvas images or screenshot if available
    ocr_summary = (request.ocr_summary or "").strip()
    if not ocr_summary and request.visual_telemetry and isinstance(request.visual_telemetry, dict):
        ocr_summary = (request.visual_telemetry.get("ocr_summary") or "").strip()

    if not ocr_summary and _ocr_engine.available:
        extracted_texts = []
        # Check canvas images first
        if request.canvas_images and isinstance(request.canvas_images, list):
            for c_img in request.canvas_images:
                raw_b64 = c_img.get("data_url") or c_img.get("b64") or ""
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                if raw_b64:
                    regions = _ocr_engine.extract(raw_b64)
                    if regions:
                        extracted_texts.extend([r.text for r in regions])

        # Check screenshot if canvas images had no text
        if not extracted_texts and request.sanitized_screenshot_b64:
            s_b64 = request.sanitized_screenshot_b64
            if "," in s_b64:
                s_b64 = s_b64.split(",", 1)[1]
            regions = _ocr_engine.extract(s_b64)
            if regions:
                extracted_texts.extend([r.text for r in regions])

        if extracted_texts:
            ocr_summary = " ".join(extracted_texts).strip()
            logger.info(f"[Reason] Extracted OCR visual text: '{ocr_summary}'")

    # Build SanitizedWorldModel directly for the provider
    sanitized_model = SanitizedWorldModel(
        url=request.url,
        sanitized_url=request.url,
        title=request.title,
        sanitized_dom=core_nodes,
        formatted_dom=formatted_dom,
        a11y_summary="",
        ocr_summary=ocr_summary,
        visual_summary=visual_summary,
        visual_regions_count=visual_count,
        redacted_screenshot_b64=request.sanitized_screenshot_b64,
        detected_pii_count=redacted_count,
        pii_categories_found=[],
        instruction_context=request.instruction_context or request.instructions,
    )

    # Build action history from request
    from webveil.core.models.schema import ActionResult, BrowserAction, ActionType
    history = []
    if request.action_history:
        for idx, item in enumerate(request.action_history):
            act_type_str = str(item.get("action") or "click").lower()
            try:
                act_type = ActionType(act_type_str)
            except Exception:
                act_type = ActionType.CLICK
            b_act = BrowserAction(
                action=act_type,
                node_id=item.get("node_id"),
                text=item.get("text"),
                url=item.get("url"),
                key=item.get("key"),
                value=item.get("value"),
            )
            history.append(ActionResult(
                action=b_act,
                success=item.get("success", True),
                step_index=idx + 1,
            ))

    try:
        plan: ActionPlan = await asyncio.to_thread(
            provider.reason,
            task=request.task,
            world_model=sanitized_model,
            action_history=history,
            error_context=None,
        )

        # If primary provider returned 429 quota exhaustion, seamlessly fallback to OpenRouter
        if ("429" in (plan.thought or "") or "RESOURCE_EXHAUSTED" in (plan.thought or "")) and config.openrouter_api_key and "openrouter" not in provider.provider_name.lower():
            logger.warning("[Reason] Primary provider returned 429 quota exhausted. Seamlessly falling back to OpenRouter...")
            fb_provider = get_provider("openrouter", config.openrouter_model)
            try:
                plan = await asyncio.to_thread(
                    fb_provider.reason,
                    task=request.task,
                    world_model=sanitized_model,
                    action_history=history,
                    error_context=None,
                )
            except Exception as fb_err:
                logger.warning(f"[Reason] OpenRouter fallback failed: {fb_err}")

        raw_p = getattr(plan, "provider_used", None)
        if not raw_p or not isinstance(raw_p, str):
            raw_p = getattr(provider, "active_tier", None)
        if not raw_p or not isinstance(raw_p, str):
            raw_p = getattr(provider, "provider_name", "Local (Ollama)")
        provider_used = str(raw_p) if raw_p is not None and not hasattr(raw_p, "_mock_name") else "Local (Ollama)"
        return ReasonResponse(
            thought=plan.thought or "",
            provider_used=provider_used,
            tier_used=provider_used,
            actions=[
                ActionResponse(
                    action=a.action.value,
                    node_id=a.node_id,
                    text=a.text or a.url,
                    url=a.url or a.text,
                    key=a.key,
                    direction=a.direction,
                    amount=a.amount,
                    value=a.value,
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
            provider_used="Error",
            tier_used="Error",
            actions=[ActionResponse(action="WAIT", thought="Reasoning error, please retry")],
        )


def _format_dom_for_prompt(nodes: List[DOMNode], max_nodes: int = 250) -> str:
    """Format sanitized DOM nodes into a text representation for LLM prompt.
    Balanced budget: form controls first, headings & infobox data, then links & content.
    """
    if not nodes:
        return ""

    form_controls = []
    structural_headings = []
    content_data = []  # th, td, p, li with informative text
    links = []
    other_nodes = []

    for n in nodes:
        tag = (n.tag_name or "").lower()
        if tag in ("input", "button", "select", "textarea"):
            form_controls.append(n)
        elif tag in ("h1", "h2", "h3", "h4", "form", "main"):
            structural_headings.append(n)
        elif tag in ("th", "td", "li", "p") and n.text_content and len(n.text_content.strip()) > 2:
            content_data.append(n)
        elif tag == "a" or n.is_interactive:
            links.append(n)
        else:
            other_nodes.append(n)

    # Allocate balanced budget:
    # 1. All form controls (inputs, buttons) - critical for actions
    selected = list(form_controls)
    
    # 2. All structural headings (h1, h2, h3)
    selected.extend(structural_headings[:40])
    
    # 3. Informative content & infobox rows (th, td, p, li)
    selected.extend(content_data[:120])
    
    # 4. Interactive links (capped so thousands of Wikipedia links don't crowd out text)
    remaining = max_nodes - len(selected)
    if remaining > 0:
        selected.extend(links[:remaining])
        
    # 5. Any other remaining space
    remaining = max_nodes - len(selected)
    if remaining > 0:
        selected.extend(other_nodes[:remaining])

    # Sort back by original node_id so DOM layout order is preserved
    selected.sort(key=lambda x: x.node_id)

    lines = []
    for node in selected:
        parts = [f"[{node.node_id}]", f"<{node.tag_name}>"]
        if getattr(node, "element_id", None):
            parts.append(f'id="{node.element_id}"')
        elif getattr(node, "element_name", None):
            parts.append(f'name="{node.element_name}"')
        if getattr(node, "element_type", None):
            parts.append(f'type="{node.element_type}"')
        if getattr(node, "placeholder", None):
            parts.append(f'placeholder="{node.placeholder}"')
        if getattr(node, "value", None):
            parts.append(f'value="{node.value[:60]}"')
        if getattr(node, "aria_label", None):
            parts.append(f'aria-label="{node.aria_label}"')
        if node.text_content:
            parts.append(f'"{node.text_content[:120]}"')
        if node.is_interactive:
            parts.append("[interactive]")
        lines.append(" ".join(parts))

    if len(nodes) > len(selected):
        lines.append(f"... ({len(nodes) - len(selected)} passive elements omitted to preserve token window)")

    return "\n".join(lines)


# ── Entry point ──
def main():
    logger.info("Starting WebVeil Thin Reasoning Server on http://127.0.0.1:8000")
    logger.info("This server does ONLY reasoning. No Playwright, no vault, no PII detection.")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
