"""
Deterministic & Task-Aware DOM Ranker.
Compresses raw DOM trees down to essential interactive, semantic, and task-relevant elements.
"""

from webveil.core.intelligence.dom_ranker import TaskAwareDOMRanker

# Backward-compatibility alias for agent loop and existing callers
class DOMRanker(TaskAwareDOMRanker):
    """
    Task-aware DOM pruner and ranker.
    Filters out non-visible nodes and non-interactive empty containers,
    prioritizing task-relevant inputs, buttons, and semantic landmarks.
    """
    pass
