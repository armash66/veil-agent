"""
WebVeil Task-Aware DOM Intelligence Subsystem.
Provides feature-based DOM ranking, token budget-aware context compression,
and action type prediction.
"""

from webveil.core.intelligence.dom_ranker import TaskAwareDOMRanker
from webveil.core.intelligence.context_compressor import ContextCompressor
from webveil.core.intelligence.action_predictor import ActionPredictor

__all__ = [
    "TaskAwareDOMRanker",
    "ContextCompressor",
    "ActionPredictor",
]
