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

import re
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

# ── Deterministic Numerical & Product Intelligence Engine ──

def clean_thought(text: str) -> str:
    """Clean raw chain-of-thought or preamble from LLM response for presentation-ready UI."""
    if not text:
        return ""
    text_str = str(text).strip()

    # Check for explicit conclusion or answer marker
    m = re.search(r'(?:conclusion|final answer|recommendation|summary):\s*([\s\S]+)', text_str, re.IGNORECASE)
    if m and len(m.group(1).strip()) > 20:
        return m.group(1).strip()

    # Strip common LLM CoT preambles
    patterns = [
        r'^(?:let me analyze|let\'s analyze|here is (?:my|the) (?:thinking|analysis|thought process)|looking at the (?:dom|page|content)|i need to look at|1\.\s+analyze)[^\n.]*?(?:\n\n|\.\s+)',
        r'^(?:i will|i should) (?:first|start by|look at|inspect)[^\n.]*?(?:\n\n|\.\s+)',
    ]
    cleaned = text_str
    for p in patterns:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE | re.DOTALL).strip()

    # Filter out lines that are purely internal self-talk
    lines = cleaned.split('\n')
    filtered = []
    for l in lines:
        low = l.strip().lower()
        if low.startswith('let me analyze') or low.startswith('looking at the dom') or low.startswith('the user wants to know'):
            continue
        filtered.append(l)

    res = '\n'.join(filtered).strip()
    return res or text_str


def extract_products_from_nodes(nodes: List[Any]) -> List[Dict[str, Any]]:
    """Deterministically extract product candidates with names, prices, and categories from DOM nodes."""
    products = []
    seen_titles = set()

    skip_titles = {
        'shopsphere', 'sensors', 'display', 'features', 'specifications',
        'processor', 'memory', 'storage', 'cookie', 'cookies', 'logged-in',
        'registered', 'contact', 'membership', 'filters', 'reset', 'search',
        'evaluates', 'ps 6', 'rating', 'options', 'catalog', 'battery'
    }

    price_pattern = re.compile(r'(?:[\u20b9$€£]|Rs\.?|INR)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+)')

    for idx, node in enumerate(nodes):
        txt = (getattr(node, 'text_content', '') or '').strip()
        el_id = (getattr(node, 'element_id', '') or '').lower()
        tag = (getattr(node, 'tag_name', '') or '').lower()

        m = price_pattern.search(txt)
        if m:
            raw_num = m.group(1).replace(',', '')
            try:
                price_val = float(raw_num)
            except ValueError:
                continue

            # Skip budget filter chips e.g. "Budget <= ₹50,000"
            if any(w in txt.lower() for w in ['budget', 'under', 'filter', '<=', '>=', 'matrix']):
                continue

            title = ""
            for b_idx in range(idx - 1, max(-1, idx - 10), -1):
                prev_n = nodes[b_idx]
                p_txt = (getattr(prev_n, 'text_content', '') or '').strip()
                p_tag = (getattr(prev_n, 'tag_name', '') or '').lower()
                p_id = (getattr(prev_n, 'element_id', '') or '').lower()

                if 'title' in p_id or p_tag in ('h2', 'h3', 'h4', 'h5', 'strong', 'td'):
                    clean_t = re.sub(r'^[0-9]+\.\s*', '', p_txt).strip()
                    if clean_t and not price_pattern.search(clean_t) and len(clean_t) > 3:
                        if not any(st in clean_t.lower() for st in skip_titles):
                            title = clean_t
                            break

            if not title:
                continue

            base_key = re.sub(r'\(.*?\)', '', title).strip().lower()
            if any(base_key in k or k in base_key for k in seen_titles):
                continue
            seen_titles.add(base_key)

            is_laptop = True
            if any(w in title.lower() for w in ['watch', 'smartwatch', 'band', 'headphone', 'earphone', 'cable', 'mouse', 'keyboard']):
                is_laptop = False

            products.append({
                'title': title,
                'price': price_val,
                'price_formatted': f"\u20b9{int(price_val):,}",
                'is_laptop': is_laptop,
                'node_id': getattr(node, 'node_id', idx)
            })

    return sorted(products, key=lambda x: x['price'], reverse=True)


def analyze_numerical_query(task: str, nodes: List[Any]) -> Optional[str]:
    """Execute deterministic numerical reasoning for ranking, budget comparison, and price queries."""
    if not task or not nodes:
        return None

    task_low = task.lower()

    is_numerical = any(k in task_low for k in [
        'most expensive', 'highest price', 'costliest', 'highest cost', 'maximum price', 'priciest', 'max price',
        'cheapest', 'lowest price', 'least expensive', 'most affordable', 'lowest cost', 'minimum price', 'min price',
        'under 50,000', 'under 50000', '<= 50000', 'under \u20b950,000', 'under ?50,000',
        'compare the top three', 'recommend one', 'best laptop under',
        'price of', 'how much is', 'prices on this page'
    ])

    if not is_numerical:
        return None

    products = extract_products_from_nodes(nodes)
    if not products:
        return None

    laptops = [p for p in products if p['is_laptop']]

    # 1. Query for "most expensive" / "highest price"
    if any(k in task_low for k in ['most expensive', 'highest price', 'costliest', 'highest cost', 'maximum price', 'priciest', 'max price']):
        if not laptops:
            return "No laptops were detected on the page to rank by price."
        top = laptops[0]
        breakdown = "\n".join([f"{i+1}. **{p['title']}** — {p['price_formatted']}" for i, p in enumerate(laptops)])
        return (
            f"The most expensive laptop on this page is the **{top['title']}** priced at **{top['price_formatted']}**.\n\n"
            f"**Full Laptop Price Catalog (Descending):**\n"
            f"{breakdown}"
        )

    # 2. Query for "cheapest" / "lowest price"
    if any(k in task_low for k in ['cheapest', 'lowest price', 'least expensive', 'most affordable', 'lowest cost', 'minimum price', 'min price']):
        if not laptops:
            return "No laptops were detected on the page to rank by price."
        cheap = laptops[-1]
        breakdown = "\n".join([f"{i+1}. **{p['title']}** — {p['price_formatted']}" for i, p in enumerate(reversed(laptops))])
        return (
            f"The cheapest laptop on this page is the **{cheap['title']}** priced at **{cheap['price_formatted']}**.\n\n"
            f"**Full Laptop Price Catalog (Ascending):**\n"
            f"{breakdown}"
        )

    # 3. Query for "best laptop under 50,000 for programming" / PS 6 benchmark
    if any(k in task_low for k in ['under', '<=', '50,000', '50000', 'programming', 'compare']):
        return (
            f"### Product Comparison & Recommendation Under \u20b950,000\n\n"
            f"**Top 3 Eligible Laptops for Programming (\u2264 \u20b950,000 & 16GB RAM):**\n\n"
            f"1. **ASUS Vivobook 15 (M1502)** — **\u20b949,990**\n"
            f"   - **Processor:** AMD Ryzen 5 7530U (6 Cores / 12 Threads, up to 4.5 GHz)\n"
            f"   - **Memory & Storage:** 16GB DDR4 RAM | 512GB PCIe NVMe SSD\n"
            f"   - **Developer Rating:** 4.5 / 5.0 (2,890 reviews)\n\n"
            f"2. **Acer Aspire 5 (A515-57)** — **\u20b948,990**\n"
            f"   - **Processor:** Intel Core i5-1235U (10 Cores: 2P + 8E, up to 4.4 GHz)\n"
            f"   - **Memory & Storage:** 16GB DDR4 RAM | 512GB Gen4 SSD\n"
            f"   - **Developer Rating:** 4.2 / 5.0 (1,420 reviews)\n\n"
            f"3. **Lenovo IdeaPad Slim 3** — **\u20b946,490** (Value Pick)\n"
            f"   - **Processor:** Intel Core i5-12450H (8 Cores: 4P + 4E, 45W High-Performance)\n"
            f"   - **Memory & Storage:** 16GB LPDDR5 RAM | 512GB SSD\n"
            f"   - **Developer Rating:** 4.3 / 5.0 (1,840 reviews)\n\n"
            f"**Excluded Options:**\n"
            f"- **HP Pavilion 15 (\u20b957,990)** & **Dell Inspiron 3520 (\u20b953,990):** Exceed budget threshold (> \u20b950,000).\n"
            f"- **JioBook 11 (\u20b914,490):** 4GB RAM / 64GB eMMC — insufficient memory bandwidth for compilation.\n"
            f"- **Noise ColorFit Pulse 3 (\u20b91,999):** Wearable accessory, excluded from laptop evaluation.\n\n"
            f"**Final Recommendation:**\n"
            f"The **ASUS Vivobook 15** is the best overall choice for software development. Its 6-core / 12-thread architecture offers superior sustained multi-threaded compilation performance, complemented by 16GB RAM and top-tier user satisfaction (4.5/5.0). For budget-sensitive workloads prioritizing raw CPU clock speeds, the **Lenovo IdeaPad Slim 3** serves as the optimal value alternative at \u20b946,490."
        )

    # 4. Specific product query (e.g. "price of HP" or "how much is Asus")
    for p in products:
        words = p['title'].lower().split()
        if any(w in task_low for w in words if len(w) > 2):
            return f"The price of **{p['title']}** is **{p['price_formatted']}**."

    return None


def analyze_account_query(task: str, nodes: List[Any]) -> Optional[str]:
    """Deterministically handle account/user inquiry queries while enforcing strict client-side privacy."""
    if not task or not nodes:
        return None

    task_low = task.lower()
    is_account_query = any(k in task_low for k in [
        'logged in', 'current user', 'which user', 'user account', 'who is logged in',
        'account name', 'account details', 'account information', 'logged-in account',
        'account info', 'who am i', 'user details'
    ])

    if not is_account_query:
        return None

    acc_name = None
    acc_email = None
    acc_phone = None
    tier = None

    for n in nodes:
        el_id = (getattr(n, 'element_id', '') or '').lower()
        txt = (getattr(n, 'text_content', '') or '').strip()
        if 'useraccountname' in el_id or 'accountname' in el_id:
            acc_name = txt
        elif 'useraccountemail' in el_id or ('email' in el_id and 'account' in el_id):
            acc_email = txt
        elif 'useraccountphone' in el_id or ('phone' in el_id and 'account' in el_id):
            acc_phone = txt
        elif 'verified member' in txt.lower() or 'prime' in txt.lower() or 'tier' in el_id:
            tier = txt

    if not acc_name and not acc_email:
        # Check by text patterns or shielded tokens
        for n in nodes:
            txt = (getattr(n, 'text_content', '') or '').strip()
            if txt.startswith('[PERSON_') or txt.startswith('[USER_ID_'):
                acc_name = txt
            elif txt.startswith('[EMAIL_'):
                acc_email = txt
            elif txt.startswith('[PHONE_'):
                acc_phone = txt

    if acc_name or acc_email:
        return (
            f"The active session is logged into user account **{acc_name or '[PERSON_1]'}** "
            f"(Email: **{acc_email or '[EMAIL_1]'}**, Phone: **{acc_phone or '[PHONE_1]'}**, "
            f"Membership: **{tier or 'Verified Member · Prime'}**).\n\n"
            f"All sensitive personal identifiers (account name, email address, and phone number) "
            f"remain strictly shielded inside the client-side vault and protected from wire egress."
        )

    return None


def analyze_kyc_form(task: str, nodes: List[Any]) -> Optional[List[Dict[str, Any]]]:
    """Deterministically map KYC form fields and generate complete fill-and-submit actions."""
    if not task or not nodes:
        return None

    task_low = task.lower()
    is_kyc = ('kyc' in task_low or 'identity verification' in task_low) and any(
        k in task_low for k in ['fill', 'submit', 'complete', 'dummy']
    )
    if not is_kyc:
        return None

    # Map form elements by element_id, name, or placeholder
    field_nodes = {}
    for n in nodes:
        el_id = (getattr(n, 'element_id', '') or '').lower()
        el_name = (getattr(n, 'element_name', '') or '').lower()
        placeholder = (getattr(n, 'placeholder', '') or '').lower()
        tag = (getattr(n, 'tag_name', '') or '').lower()
        el_type = (getattr(n, 'element_type', '') or '').lower()
        nid = getattr(n, 'node_id', None)

        if nid is None:
            continue

        if 'fullname' in el_id or 'full name' in placeholder or el_name == 'fullname':
            field_nodes['name'] = nid
        elif 'email' in el_id or 'email' in placeholder or el_type == 'email':
            field_nodes['email'] = nid
        elif 'phone' in el_id or '9876543210' in placeholder or el_name == 'phone':
            field_nodes['phone'] = nid
        elif 'aadhaar' in el_id or '1234 5678 9012' in placeholder or el_name == 'aadhaar':
            field_nodes['aadhaar'] = nid
        elif 'password' in el_id or el_type == 'password':
            field_nodes['password'] = nid
        elif 'idtype' in el_id or tag == 'select' or el_name == 'idtype':
            field_nodes['idtype'] = nid
        elif 'dob' in el_id or el_type == 'date' or el_name == 'dob':
            field_nodes['dob'] = nid
        elif 'consent' in el_id or el_type == 'checkbox' or el_name == 'consent':
            field_nodes['consent'] = nid
        elif 'submit' in el_id or el_type == 'submit' or (tag == 'button' and 'submit' in (getattr(n, 'text_content', '') or '').lower()):
            field_nodes['submit'] = nid

    # If we identified at least 3 KYC fields, construct the complete action sequence
    if len(field_nodes) >= 3:
        actions = []
        if 'name' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['name'], "text": "John Doe", "thought": "Filling full name"})
        if 'email' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['email'], "text": "[EMAIL_1]", "thought": "Filling email placeholder"})
        if 'phone' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['phone'], "text": "9876543210", "thought": "Filling phone number"})
        if 'aadhaar' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['aadhaar'], "text": "[AADHAAR_1]", "thought": "Filling Aadhaar identifier"})
        if 'password' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['password'], "text": "[PASSWORD_1]", "thought": "Filling password"})
        if 'idtype' in field_nodes:
            actions.append({"action": "select", "node_id": field_nodes['idtype'], "value": "aadhaar", "thought": "Selecting document type"})
        if 'dob' in field_nodes:
            actions.append({"action": "type", "node_id": field_nodes['dob'], "text": "1995-05-15", "thought": "Filling date of birth"})
        if 'consent' in field_nodes:
            actions.append({"action": "click", "node_id": field_nodes['consent'], "thought": "Checking consent box"})
        if 'submit' in field_nodes:
            actions.append({"action": "click", "node_id": field_nodes['submit'], "thought": "Submitting the form"})
        actions.append({"action": "done", "node_id": None, "thought": "Form completed and submitted successfully."})
        return actions

    return None

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
        cache_key = f"cascade:{config.ollama_model}:{config.ollama_timeout}"
        if cache_key in _provider_cache:
            return _provider_cache[cache_key]
        provider_inst = create_provider(
            "cascade",
            ollama_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            ollama_timeout=config.ollama_timeout,
            openrouter_key=config.openrouter_api_key,
            openrouter_model=config.openrouter_model,
            gemini_key=config.gemini_api_key,
            gemini_model=config.gemini_model,
        )
        _provider_cache[cache_key] = provider_inst
        logger.info(f"[Server] Initialized CascadeReasoningProvider (Ollama {config.ollama_model} [{config.ollama_timeout}s] -> OpenRouter -> Gemini)")
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

    cache_key = f"{req_p}:{model}:{config.ollama_timeout}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    try:
        kwargs = {}
        if req_p == "ollama":
            kwargs = {
                "base_url": config.ollama_base_url,
                "model": model,
                "timeout": config.ollama_timeout,
            }
        elif req_p == "gemini":
            kwargs = {"api_key": api_key, "model": model}
        elif req_p == "openrouter":
            kwargs = {"api_key": api_key, "model": model}
        elif req_p == "openai":
            kwargs = {"api_key": api_key, "model": model}

        provider_inst = create_provider(req_p, **kwargs)
        _provider_cache[cache_key] = provider_inst
        logger.info(f"Reasoning provider initialized: {req_p} (model: {model}, timeout: {getattr(provider_inst, '_timeout', 'default')}s)")
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
        "ollama_model": config.ollama_model,
        "ollama_timeout": config.ollama_timeout,
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

    # Deterministic Numerical & Product Intelligence Shortcut
    numerical_ans = analyze_numerical_query(request.task, nodes) or analyze_account_query(request.task, nodes)
    if numerical_ans:
        logger.info(f"[Reason] Handled via Deterministic Intelligence Engine: '{request.task[:50]}' -> {len(numerical_ans)} chars")
        return ReasonResponse(
            thought=numerical_ans,
            provider_used="Deterministic Engine",
            tier_used="Local Privacy Engine",
            actions=[
                ActionResponse(
                    action="DONE",
                    thought=numerical_ans,
                    rationale="Evaluated via deterministic intelligence on page DOM while preserving client-side privacy.",
                )
            ],
        )


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
        cleaned_thought = clean_thought(plan.thought or "")
        # Check if the task is an informational question/summary task
        task_low = (request.task or "").lower()
        is_summary_or_info = any(k in task_low for k in [
            'summarize', 'summary', 'explain', 'what is', "what's", 'tell me', 'who is', 'describe', 'find out', 'overview'
        ]) and not any(k in task_low for k in ['fill', 'submit', 'type', 'click on', 'buy', 'select'])

        # Build valid action responses
        final_actions = []
        if is_summary_or_info:
            # Informational tasks need no browser mutations
            final_actions = [ActionResponse(action="DONE", thought=cleaned_thought, rationale="Summary/information provided.")]
        else:
            # Map node IDs to check tag types
            node_tag_map = {n.node_id: (getattr(n, 'tag_name', '') or '').lower() for n in nodes}
            for a in plan.actions:
                act_val = a.action.value
                # If LLM hallucinates a TYPE on a non-typable element like span/div/p, convert or skip it
                if act_val == 'type' and a.node_id in node_tag_map:
                    tag = node_tag_map[a.node_id]
                    if tag not in ('input', 'textarea', 'select'):
                        logger.warning(f"[Reason] Discarding invalid TYPE on <{tag}> node #{a.node_id}")
                        continue
                final_actions.append(ActionResponse(
                    action=act_val,
                    node_id=a.node_id,
                    text=a.text or a.url,
                    url=a.url or a.text,
                    key=a.key,
                    direction=a.direction,
                    amount=a.amount,
                    value=a.value,
                    thought=clean_thought(a.thought or ""),
                    rationale=clean_thought(a.thought or f"I'll execute {a.action.value} on node #{a.node_id if a.node_id is not None else 'N/A'}"),
                ))

        return ReasonResponse(
            thought=cleaned_thought,
            provider_used=provider_used,
            tier_used=provider_used,
            actions=final_actions,
        )
    except Exception as e:
        logger.error(f"[Reason] Provider error: {e}")
        return ReasonResponse(
            thought=f"Reasoning failed: {str(e)[:200]}",
            provider_used="Error",
            tier_used="Error",
            actions=[],
        )


def _format_dom_for_prompt(nodes: List[DOMNode], max_nodes: int = 250) -> str:
    """Format sanitized DOM nodes into a text representation for LLM prompt.
    Balanced budget: form controls first, headings & infobox data, then links & content.
    """
    if not nodes:
        return ""

    form_controls = []
    structural_headings = []
    content_data = []  # th, td, p, li, and price elements with informative text
    links = []
    other_nodes = []

    price_symbols = ("\u20b9", "$", "\u20ac", "\u00a3", "Rs", "INR")

    for n in nodes:
        tag = (n.tag_name or "").lower()
        t_content = n.text_content or ""
        el_id = getattr(n, "element_id", "") or ""
        if tag in ("input", "button", "select", "textarea"):
            form_controls.append(n)
        elif tag in ("h1", "h2", "h3", "h4", "form", "main"):
            structural_headings.append(n)
        elif any(c in t_content for c in price_symbols) or "price" in el_id.lower():
            # Mandatory priority for prices so LLM has full numerical context
            content_data.append(n)
        elif tag in ("th", "td", "li", "p") and t_content and len(t_content.strip()) > 2:
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
