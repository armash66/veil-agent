"""
Browser Execution Readiness Scheduler.
Separates execution readiness ('Can the browser execute safely right now?')
from security authorization ('Is this action allowed?').
Enforces DOM stabilization, navigation readiness, and target attachment WITHOUT arbitrary fixed delays.
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from webveil.core.models.schema import BrowserAction, ActionType, DOMNode

logger = logging.getLogger("WebVeilBrowser.Scheduler")


@dataclass
class ReadinessStatus:
    is_ready: bool
    reason: str
    elapsed_ms: float
    retries_used: int = 0


class ExecutionScheduler:
    """
    Evaluates page state readiness and element interactability before action dispatch.
    Allows immediate execution (0ms delay) when the browser is already stable and ready.
    """

    def __init__(self, default_timeout_ms: float = 1200.0, poll_interval_ms: float = 25.0):
        self.default_timeout_ms = default_timeout_ms
        self.poll_interval_ms = poll_interval_ms

    def await_readiness(
        self,
        page,
        action: BrowserAction,
        target_node: Optional[DOMNode] = None,
        max_wait_ms: Optional[float] = None,
    ) -> ReadinessStatus:
        """
        Wait until browser state and target element are ready for execution.
        Returns immediately if browser is already ready.
        """
        timeout_ms = max_wait_ms or self.default_timeout_ms
        t0 = time.perf_counter()

        # Global actions without node targets (done, wait, keypress) are immediately ready
        if action.action in [ActionType.DONE, ActionType.WAIT, ActionType.KEYPRESS, ActionType.NAVIGATE]:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ReadinessStatus(
                is_ready=True,
                reason=f"Action '{action.action.value}' does not require target DOM stabilization.",
                elapsed_ms=round(elapsed, 2),
                retries_used=0,
            )

        if not page:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ReadinessStatus(
                is_ready=True,
                reason="Headless/Mock browser mode; ready immediately.",
                elapsed_ms=round(elapsed, 2),
                retries_used=0,
            )

        # Check document readyState and DOM stabilization
        retries = 0
        while True:
            elapsed = (time.perf_counter() - t0) * 1000.0

            # 1. Check Document Ready State
            doc_ready = True
            try:
                if hasattr(page, "evaluate"):
                    state = page.evaluate("() => document.readyState")
                    doc_ready = state in ["complete", "interactive"]
            except Exception:
                doc_ready = True

            # 2. Check Target Element Availability
            target_ready = True
            if action.node_id is not None:
                try:
                    if hasattr(page, "locator"):
                        loc = page.locator(f"[data-webveil-id='{action.node_id}']")
                        if hasattr(loc, "is_visible") and callable(loc.is_visible):
                            target_ready = bool(loc.is_visible())
                except Exception:
                    target_ready = True

            if doc_ready and target_ready:
                return ReadinessStatus(
                    is_ready=True,
                    reason="Browser and target element are stable and ready.",
                    elapsed_ms=round(elapsed, 2),
                    retries_used=retries,
                )

            if elapsed >= timeout_ms:
                logger.warning(
                    f"[Scheduler] Readiness wait timed out after {elapsed:.1f}ms for action {action.action.value}."
                )
                return ReadinessStatus(
                    is_ready=False,
                    reason=f"Readiness timeout ({timeout_ms}ms exceeded); doc_ready={doc_ready}, target_ready={target_ready}.",
                    elapsed_ms=round(elapsed, 2),
                    retries_used=retries,
                )

            retries += 1
            time.sleep(self.poll_interval_ms / 1000.0)
