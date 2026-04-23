"""Metrics: deterministic scorers and LLM-judge wrappers.

A `Metric` is anything with an async `score(predicted, expected) -> float`
method. `RubricCritic` wraps an `Agent[Candidate, Score]` so an LLM
judge can stand in as a metric. `CostTracker` is an observer-style
aggregator rather than a per-row scorer; it lives here because it
summarises evaluation runs.
"""

from __future__ import annotations

from .base import Metric
from .contains import Contains
from .cost import CostTracker
from .deterministic import ExactMatch, JsonValid, Latency
from .regex_match import RegexMatch
from .rouge import Rouge1
from .rubric_critic import RubricCritic

__all__ = [
    "Contains",
    "CostTracker",
    "ExactMatch",
    "JsonValid",
    "Latency",
    "Metric",
    "RegexMatch",
    "Rouge1",
    "RubricCritic",
]
