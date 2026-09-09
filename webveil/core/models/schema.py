"""
Core Data Schemas for WebVeil Agent & Privacy Pipeline.
V1: Extended with LocalWorldModel, ActionPlan, and provider abstractions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


# ─── PII & Privacy Types (V0, unchanged) ────────────────────────────────

class PIICategory(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    AADHAAR = "AADHAAR"
    CREDIT_CARD = "CARD"
    PASSWORD = "PASSWORD"
    NAME = "NAME"
    SSN = "SSN"
    SECRET = "SECRET"


@dataclass
class PIIMatch:
    category: PIICategory
    raw_value: str
    placeholder: str
    source_node_id: Optional[int] = None
    bounding_box: Optional[Dict[str, float]] = None  # {x, y, width, height}
    context: str = ""


@dataclass
class VaultEntry:
    token: str  # e.g., "[PASSWORD_1]"
    secret: str  # raw secret
    origin: str  # domain origin
    category: PIICategory
    source_node_id: Optional[int] = None
    element_type: str = "input"
    element_id: Optional[str] = None
    element_name: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)


# ─── DOM Types (V0, unchanged) ──────────────────────────────────────────

@dataclass
class DOMNode:
    node_id: int
    tag_name: str
    element_type: Optional[str] = None
    element_id: Optional[str] = None
    name: Optional[str] = None
    text_content: str = ""
    value: str = ""
    is_interactive: bool = False
    is_visible: bool = True
    bounding_box: Optional[Dict[str, float]] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    placeholder_assigned: Optional[str] = None


# ─── Observation Types (V1, new) ────────────────────────────────────────

@dataclass
class TextRegion:
    """Text detected by OCR that may not exist in the DOM."""
    text: str
    bounding_box: Dict[str, float]  # {x, y, width, height}
    confidence: float = 0.0
    source: str = "ocr"  # "ocr" | "canvas" | "svg"


@dataclass
class LocalWorldModel:
    """
    Unified local observation merging DOM + Accessibility + Visual layers.
    This is the raw local state BEFORE privacy processing.
    """
    url: str
    title: str
    dom_nodes: List[DOMNode]
    formatted_dom: str
    a11y_tree: Optional[Dict[str, Any]] = None
    a11y_summary: str = ""
    ocr_regions: List[TextRegion] = field(default_factory=list)
    screenshot_b64: str = ""
    page_text: str = ""
    timestamp: float = 0.0


@dataclass
class SanitizedWorldModel:
    """
    Privacy-processed world model. All PII replaced with placeholders.
    This is the ONLY representation that may leave the device.
    """
    url: str
    sanitized_url: str
    title: str
    sanitized_dom: List[DOMNode]
    formatted_dom: str
    a11y_summary: str = ""
    ocr_summary: str = ""
    redacted_screenshot_b64: Optional[str] = None
    detected_pii_count: int = 0
    pii_categories_found: List[str] = field(default_factory=list)


# ─── Legacy Observation Type (V0 compatibility) ────────────────────────

@dataclass
class SanitizedObservation:
    """V0 compatibility wrapper. Used by existing egress gate and tests."""
    url: str
    sanitized_url: str
    title: str
    dom_tree: List[DOMNode]
    formatted_dom: str
    redacted_screenshot_b64: Optional[str] = None
    detected_pii_count: int = 0
    pii_categories_found: List[str] = field(default_factory=list)


# ─── Action Types (V1, extended) ────────────────────────────────────────

class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    KEYPRESS = "keypress"
    SELECT = "select"
    WAIT = "wait"
    DONE = "done"


@dataclass
class BrowserAction:
    action: ActionType
    node_id: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    url: Optional[str] = None
    direction: Optional[str] = "down"
    amount: Optional[int] = 300
    value: Optional[str] = None  # For SELECT action
    thought: Optional[str] = None  # LLM reasoning transparency
    placeholder_restored: bool = False


@dataclass
class ActionResult:
    """Result of executing a single action."""
    action: BrowserAction
    success: bool
    error: Optional[str] = None
    step_index: int = 0


@dataclass
class ActionPlan:
    """
    1-N proposed actions from the reasoning engine.
    The local firewall validates each action individually before execution.
    """
    actions: List[BrowserAction]
    thought: str = ""  # Overall reasoning for this plan
    confidence: float = 0.0


# ─── Egress Types (V0, unchanged) ──────────────────────────────────────

@dataclass
class EgressPayload:
    task: str
    observation: SanitizedObservation
    action_history: List[Dict[str, Any]]


# ─── Provider Types (V1, new) ──────────────────────────────────────────

@dataclass
class TokenUsage:
    """Tracks LLM token consumption for SIH resource metrics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_calls: int = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ─── Metrics Types (V0, unchanged) ─────────────────────────────────────

@dataclass
class StageLatencies:
    dom_extraction_ms: float = 0.0
    pii_detection_ms: float = 0.0
    redaction_ms: float = 0.0
    egress_audit_ms: float = 0.0
    server_reasoning_ms: float = 0.0
    firewall_execution_ms: float = 0.0
    verification_ms: float = 0.0
    a11y_extraction_ms: float = 0.0
    ocr_extraction_ms: float = 0.0
    world_model_build_ms: float = 0.0


@dataclass
class SIHMetrics:
    visual_accuracy: float = 0.0       # 25% weight
    pii_precision: float = 0.0
    pii_recall: float = 0.0
    pii_f1_score: float = 0.0          # 20% weight (PII Detection)
    redaction_precision: float = 0.0   # 20% weight
    resource_score: float = 0.0        # 20% weight (RAM & CPU benchmark score)
    latency_score: float = 0.0         # 15% weight (Speed benchmark score)
    overall_sih_score: float = 0.0     # Weighted 100% total
    
    python_memory_mb: float = 0.0
    chromium_memory_mb: float = 0.0
    combined_peak_memory_mb: float = 0.0
    average_cpu_percent: float = 0.0
    peak_cpu_percent: float = 0.0
    
    end_to_end_latency_ms: float = 0.0
    stage_latencies: StageLatencies = field(default_factory=StageLatencies)
    llm_call_count: int = 0
    llm_total_tokens: int = 0


# ─── Phase 3 Intelligence & Stage Types (V1.5, new) ────────────────────


@dataclass
class TaskRepresentation:
    """Structured local NLP representation of user task."""
    raw_prompt: str
    intent: str  # e.g., "product_search", "information_retrieval", "form_fill"
    entities: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    count: Optional[int] = None
    objective: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    confidence: float = 0.95


@dataclass
class DOMRankingMetrics:
    """Task-aware DOM intelligence & context compression statistics."""
    raw_nodes: int = 0
    filtered_nodes: int = 0
    compression_ratio: float = 0.0  # e.g., 96.3%
    estimated_tokens_saved: int = 0
    ranking_latency_ms: float = 0.0


@dataclass
class PrivacyDecision:
    """Hybrid local PII detection decision enforcing deterministic precedence."""
    entity_type: str
    raw_value: str
    placeholder: str
    confidence: float
    sources: List[str]  # ["regex"], ["metadata"], ["ner"]
    action: str = "REDACT"
    source_node_id: Optional[int] = None


@dataclass
class GroundingResult:
    """Local element grounding decision between LLM proposal and firewall."""
    action: BrowserAction
    selected_node_id: Optional[int]
    confidence: float  # 0.0 to 1.0
    alternative_nodes: List[Dict[str, Any]] = field(default_factory=list)
    threshold_action: str = "EXECUTE"  # "EXECUTE" (>=0.85), "VERIFY" (0.60-0.84), "REPLAN" (<0.60)
    reasoning: str = ""



# Re-export state machine abstractions
from webveil.core.models.state import AgentStage, AgentState, AgentEvent

