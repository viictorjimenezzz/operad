"""Metrics: deterministic scorers.

A `Metric` is anything with an async `score(predicted, expected) -> float`
method. LLM-judge metrics live one level up: `operad.components.Critic`
is an `Agent[Candidate, Score]`, and `operad.algorithms.BestOfN` uses it
as a judge. The ``Metric`` protocol here covers only the pure-Python
scorers that don't need a build step.
"""

from __future__ import annotations

from .base import Metric
from .deterministic import ExactMatch, JsonValid, Latency

__all__ = ["ExactMatch", "JsonValid", "Latency", "Metric"]
