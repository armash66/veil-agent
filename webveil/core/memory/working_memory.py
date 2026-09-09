"""
Local Agent Working Memory.
Maintains browser-local state, persistent task intent, subgoals,
structured action and failure history, verification state, and privacy tiers.
Enforces the invariant: Sensitive information remains strictly local.
"""

import time
import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional

from webveil.core.models.schema import BrowserAction, ActionType, ActionResult, DOMNode, TaskRepresentation
from webveil.core.memory.guard import ZeroPIIMemoryGuard

logger = logging.getLogger("WebVeilMemory.WorkingMemory")


class GoalStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class FailureType(str, Enum):
    STALE_TARGET = "STALE_TARGET"
    NAVIGATION_FAILURE = "NAVIGATION_FAILURE"
    TIMEOUT = "TIMEOUT"
    POPUP = "POPUP"
    MISSING_ELEMENT = "MISSING_ELEMENT"
    FIREWALL_REJECTION = "FIREWALL_REJECTION"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class MemoryPrivacyLevel(str, Enum):
    PUBLIC = "PUBLIC"              # Safe for remote reasoning
    TOKENIZED = "TOKENIZED"        # Replaced with placeholder; safe for remote reasoning
    SENSITIVE = "SENSITIVE"        # Secret or user PII; must remain local
    LOCAL_ONLY = "LOCAL_ONLY"      # Internal engine state; never sent across network
    UNKNOWN = "UNKNOWN"            # Unclassified; treated as LOCAL_ONLY until audited


@dataclass
class SubGoal:
    goal_id: str
    description: str
    expected_outcome: str
    status: GoalStatus = GoalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    failure_reason: Optional[str] = None

    def mark_completed(self):
        self.status = GoalStatus.COMPLETED
        self.completed_at = time.time()

    def mark_failed(self, reason: str):
        self.status = GoalStatus.FAILED
        self.failure_reason = reason
        self.completed_at = time.time()


@dataclass
class ActionRecord:
    action_id: str
    action: BrowserAction
    target_node_id: Optional[int]
    timestamp: float
    precondition_summary: str
    result_success: bool
    postcondition_summary: str
    latency_ms: float
    privacy_level: MemoryPrivacyLevel = MemoryPrivacyLevel.PUBLIC
    failure_details: Optional[str] = None
    provenance: str = "agent_loop"


@dataclass
class FailureRecord:
    failure_id: str
    failure_type: FailureType
    step_index: int
    details: str
    action_attempted: Optional[str] = None
    target_node_id: Optional[int] = None
    page_url: str = ""
    timestamp: float = field(default_factory=time.time)
    recovery_attempted: bool = False


@dataclass
class VerificationRecord:
    record_id: str
    step_index: int
    expected_state: str
    actual_state: str
    verified: bool
    confidence: float
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class AgentWorkingMemory:
    """
    Structured browser-local working memory for WebVeil agents.
    Retains persistent task intent, active goal chains, environment state transitions,
    action and failure history, and verification records.
    """

    def __init__(self, guard: Optional[ZeroPIIMemoryGuard] = None, session_ttl_sec: float = 3600.0):
        self.guard = guard or ZeroPIIMemoryGuard()
        self.session_ttl_sec = session_ttl_sec

        # Task & Intent Persistence
        self.session_id: str = f"sess_{int(time.time())}"
        self.original_task: str = ""
        self.active_intent: Optional[TaskRepresentation] = None
        self.subgoals: List[SubGoal] = []
        self.current_goal_index: int = 0

        # Environment & Page State
        self.current_url: str = "about:blank"
        self.previous_url: str = "about:blank"
        self.current_title: str = ""
        self.last_observation_summary: str = ""
        self.dom_nodes_count: int = 0

        # Histories
        self.action_history: List[ActionRecord] = []
        self.failure_history: List[FailureRecord] = []
        self.verification_history: List[VerificationRecord] = []

        # Local Metadata Store (key -> {value, privacy_level, timestamp})
        self._local_store: Dict[str, Dict[str, Any]] = {}

    def set_task(self, task_prompt: str, task_rep: Optional[TaskRepresentation] = None):
        """
        Store or continue task.
        If prompt is a continuation phrase (e.g. 'ok do it', 'continue', 'proceed')
        and an active intent already exists, preserve the active intent.
        """
        continuation_phrases = ["ok do it", "do it", "continue", "proceed", "go ahead", "yes", "sure", "ok"]
        clean_prompt = task_prompt.strip().lower()

        if clean_prompt in continuation_phrases and bool(self.original_task):
            logger.info(
                f"[WorkingMemory] Continuation prompt '{task_prompt}' detected: "
                f"Preserving active task intent: '{self.original_task}'"
            )
            return

        self.original_task = task_prompt
        self.active_intent = task_rep
        self.subgoals.clear()
        self.current_goal_index = 0

        # Create primary goal from task representation
        if task_rep:
            self.add_subgoal(
                description=f"Accomplish intent: {task_rep.intent}",
                expected_outcome=task_rep.raw_prompt,
            )
        else:
            self.add_subgoal(
                description=task_prompt,
                expected_outcome="Task completion signaled",
            )

    def add_subgoal(self, description: str, expected_outcome: str) -> SubGoal:
        goal = SubGoal(
            goal_id=f"goal_{len(self.subgoals) + 1}",
            description=description,
            expected_outcome=expected_outcome,
            status=GoalStatus.ACTIVE if len(self.subgoals) == 0 else GoalStatus.PENDING,
        )
        self.subgoals.append(goal)
        return goal

    def get_active_goal(self) -> Optional[SubGoal]:
        for g in self.subgoals:
            if g.status == GoalStatus.ACTIVE:
                return g
        return None

    def advance_goal_on_success(self):
        active = self.get_active_goal()
        if active:
            active.mark_completed()
            logger.info(f"[WorkingMemory] Goal [{active.goal_id}] marked COMPLETED.")

        # Activate next pending goal
        for g in self.subgoals:
            if g.status == GoalStatus.PENDING:
                g.status = GoalStatus.ACTIVE
                logger.info(f"[WorkingMemory] Goal [{g.goal_id}] activated: '{g.description}'.")
                break

    def update_environment_state(self, url: str, title: str, dom_nodes_count: int, observation_summary: str = ""):
        """Track page transitions and detect state changes."""
        self.previous_url = self.current_url
        self.current_url = url
        self.current_title = title
        self.dom_nodes_count = dom_nodes_count
        self.last_observation_summary = observation_summary

    def record_action(
        self,
        action: BrowserAction,
        success: bool,
        step_index: int,
        latency_ms: float = 0.0,
        precondition: str = "",
        postcondition: str = "",
        failure_reason: Optional[str] = None,
        privacy_level: MemoryPrivacyLevel = MemoryPrivacyLevel.PUBLIC,
    ):
        """Record executed browser action in working memory."""
        rec = ActionRecord(
            action_id=f"act_{step_index}_{len(self.action_history) + 1}",
            action=action,
            target_node_id=action.node_id,
            timestamp=time.time(),
            precondition_summary=precondition,
            result_success=success,
            postcondition_summary=postcondition,
            latency_ms=latency_ms,
            privacy_level=privacy_level,
            failure_details=failure_reason,
        )
        self.action_history.append(rec)

    def record_failure(
        self,
        failure_type: FailureType,
        step_index: int,
        details: str,
        action: Optional[BrowserAction] = None,
    ) -> FailureRecord:
        """Record structured failure for replanning context."""
        rec = FailureRecord(
            failure_id=f"fail_{step_index}_{len(self.failure_history) + 1}",
            failure_type=failure_type,
            step_index=step_index,
            details=details,
            action_attempted=action.action.value if action else None,
            target_node_id=action.node_id if action else None,
            page_url=self.current_url,
            timestamp=time.time(),
        )
        self.failure_history.append(rec)
        logger.warning(
            f"[WorkingMemory] Recorded failure [{rec.failure_type.value}] at step {step_index}: {details[:80]}"
        )
        return rec

    def record_verification(
        self,
        step_index: int,
        expected_state: str,
        actual_state: str,
        verified: bool,
        confidence: float,
        reasons: Optional[List[str]] = None,
    ):
        """Record post-action verification result."""
        rec = VerificationRecord(
            record_id=f"ver_{step_index}_{len(self.verification_history) + 1}",
            step_index=step_index,
            expected_state=expected_state,
            actual_state=actual_state,
            verified=verified,
            confidence=confidence,
            reasons=reasons or [],
            timestamp=time.time(),
        )
        self.verification_history.append(rec)

    def get_recent_failures(self, max_count: int = 3) -> List[FailureRecord]:
        return self.failure_history[-max_count:]

    def get_sanitized_summary_for_reasoning(self) -> Dict[str, Any]:
        """
        Build minimal context payload from working memory for remote reasoning.
        Omits sensitive and local-only items.
        """
        active_goal = self.get_active_goal()
        recent_failures = [
            f"{f.failure_type.value}: {f.details}" for f in self.get_recent_failures(2)
        ]

        return {
            "task": self.original_task,
            "active_goal": active_goal.description if active_goal else self.original_task,
            "current_url": self.current_url,
            "page_title": self.current_title,
            "recent_failures": recent_failures,
            "actions_executed_count": sum(1 for a in self.action_history if a.result_success),
        }

    def reset_session(self):
        """Reset session working memory while honoring local boundaries."""
        self.action_history.clear()
        self.failure_history.clear()
        self.verification_history.clear()
        self.subgoals.clear()
        self.original_task = ""
        self.active_intent = None
        self._local_store.clear()
        logger.info("[WorkingMemory] Session reset completed.")
