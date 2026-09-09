"""
Structured Agent State & Stage Machine.
Enforces typed state transitions across the 11 explicit stages:
UNDERSTAND → OBSERVE → FILTER → PROTECT → REASON → GROUND → AUTHORIZE → ACT → VERIFY → UPDATE_STATE → REPLAN / DONE
"""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import (
    DOMNode, BrowserAction, ActionResult, ActionPlan,
    PIIMatch, LocalWorldModel, SanitizedWorldModel,
    TaskRepresentation,
)


class AgentStage(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    OBSERVE = "OBSERVE"
    FILTER = "FILTER"
    PROTECT = "PROTECT"
    REASON = "REASON"
    GROUND = "GROUND"
    AUTHORIZE = "AUTHORIZE"
    ACT = "ACT"
    VERIFY = "VERIFY"
    UPDATE_STATE = "UPDATE_STATE"
    REPLAN = "REPLAN"
    DONE = "DONE"

    # Backward-compatibility alias
    PERCEIVE = "OBSERVE"


@dataclass
class AgentEvent:
    """
    Structured observability event emitted at each stage of the agent loop.
    Security Invariant: NEVER contains raw sensitive PII values.
    """
    stage: str
    status: str  # "started", "completed", "failed", "blocked"
    step: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "step": self.step,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class AgentState:
    """
    Complete, observable, persistent-in-session agent state.
    Carries full execution context across loop iterations.
    """
    task: str
    task_representation: Optional[TaskRepresentation] = None
    current_url: str = ""
    current_page: Any = None
    observation: Optional[LocalWorldModel] = None
    selected_elements: List[DOMNode] = field(default_factory=list)
    privacy_results: List[PIIMatch] = field(default_factory=list)
    sanitized_observation: Optional[SanitizedWorldModel] = None
    reasoning_result: Optional[ActionPlan] = None
    proposed_actions: List[BrowserAction] = field(default_factory=list)
    executed_actions: List[ActionResult] = field(default_factory=list)
    failed_actions: List[ActionResult] = field(default_factory=list)
    verification_result: Optional[bool] = None
    step_number: int = 0
    max_steps: int = 20
    stage: AgentStage = AgentStage.UNDERSTAND
    termination_reason: Optional[str] = None
    events: List[AgentEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def emit_event(self, stage: AgentStage, status: str, metadata: Optional[Dict[str, Any]] = None) -> AgentEvent:
        """
        Record and return a structured event.
        Guarantees zero raw PII in emitted metadata.
        """
        clean_meta = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (int, float, bool)):
                    clean_meta[k] = v
                elif isinstance(v, list):
                    clean_meta[k] = [
                        item if isinstance(item, (int, float, bool))
                        else str(item)[:100]
                        for item in v
                    ]
                elif isinstance(v, dict):
                    clean_meta[k] = {
                        dk: dv for dk, dv in v.items()
                        if isinstance(dv, (int, float, bool, str))
                    }
                elif isinstance(v, str):
                    clean_meta[k] = v[:200]
                else:
                    clean_meta[k] = str(v)[:100]

        event = AgentEvent(
            stage=stage.value if hasattr(stage, "value") else str(stage),
            status=status,
            step=self.step_number,
            metadata=clean_meta,
        )
        self.events.append(event)
        return event

    def is_terminal(self) -> bool:
        """Check if agent state has reached a terminal condition."""
        return self.termination_reason is not None or self.stage == AgentStage.DONE
