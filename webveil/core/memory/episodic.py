"""
Episodic Memory for WebVeil Browser Agent.
Stores past task workflows, execution trajectories, domain patterns, and outcomes
with strict Zero-PII sanitization guarantees.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from webveil.core.memory.guard import ZeroPIIMemoryGuard

logger = logging.getLogger("WebVeilMemory.Episodic")


@dataclass
class TaskEpisodeRecord:
    session_id: str
    task_goal: str
    domains_visited: List[str] = field(default_factory=list)
    action_summary: List[str] = field(default_factory=list)
    outcome_status: str = "SUCCESS"
    duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)


class EpisodicMemory:
    """
    In-memory and persistent store of past agent task episodes.
    Enforces privacy validation before storing any episode record.
    """

    def __init__(self, guard: Optional[ZeroPIIMemoryGuard] = None):
        self.guard = guard or ZeroPIIMemoryGuard()
        self._episodes: List[TaskEpisodeRecord] = []

    def record_episode(self, episode: TaskEpisodeRecord):
        """
        Record a completed task episode after asserting zero PII is contained in texts.
        """
        # Scan task goal
        self.guard.assert_clean(episode.task_goal, context="task_goal")

        # Scan action summary strings
        for act in episode.action_summary:
            self.guard.assert_clean(act, context="action_summary")

        self._episodes.append(episode)
        logger.info(
            f"[EpisodicMemory] Recorded episode [{episode.session_id}] | "
            f"Goal: '{episode.task_goal[:40]}' | Outcome: {episode.outcome_status}"
        )

    def search_episodes(self, query: str, domain: Optional[str] = None, limit: int = 5) -> List[TaskEpisodeRecord]:
        """
        Find past similar episodes matching query keywords or domain.
        """
        q_lower = query.lower()
        results: List[TaskEpisodeRecord] = []

        for ep in reversed(self._episodes):
            if domain and not any(domain.lower() in d.lower() for d in ep.domains_visited):
                continue
            if q_lower in ep.task_goal.lower() or any(q_lower in a.lower() for a in ep.action_summary):
                results.append(ep)
                if len(results) >= limit:
                    break

        return results

    def get_success_rate(self, domain: Optional[str] = None) -> float:
        """Calculate past task success rate."""
        relevant = [
            ep for ep in self._episodes
            if not domain or any(domain.lower() in d.lower() for d in ep.domains_visited)
        ]
        if not relevant:
            return 1.0

        successes = sum(1 for ep in relevant if ep.outcome_status == "SUCCESS")
        return round(successes / len(relevant), 2)

    def clear(self):
        self._episodes.clear()
