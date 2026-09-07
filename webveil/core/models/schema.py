"""
Core Data Schemas for WebVeil Agent & Privacy Pipeline.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


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


@dataclass
class SanitizedObservation:
    url: str
    sanitized_url: str
    title: str
    dom_tree: List[DOMNode]
    formatted_dom: str
    redacted_screenshot_b64: Optional[str] = None
    detected_pii_count: int = 0
    pii_categories_found: List[str] = field(default_factory=list)


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    KEYPRESS = "keypress"
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
    placeholder_restored: bool = False


@dataclass
class EgressPayload:
    task: str
    observation: SanitizedObservation
    action_history: List[Dict[str, Any]]


@dataclass
class StageLatencies:
    dom_extraction_ms: float = 0.0
    pii_detection_ms: float = 0.0
    redaction_ms: float = 0.0
    egress_audit_ms: float = 0.0
    server_reasoning_ms: float = 0.0
    firewall_execution_ms: float = 0.0
    verification_ms: float = 0.0


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
