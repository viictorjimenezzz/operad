"""`AggregatedMetric` — reduce a list of per-row scores to one scalar."""

from __future__ import annotations

import math
import statistics
from typing import Literal

Reducer = Literal["mean", "median", "min", "max", "sum"]


class AggregatedMetric:
    """Combine a list of per-row scores into a single scalar.

    Stateless; cheap to construct. Use it when a downstream caller
    (regression check, sensitivity analysis) needs one summary number
    per metric rather than the full per-row vector.
    """

    def __init__(self, *, reducer: Reducer = "mean", name: str = "") -> None:
        self.reducer: Reducer = reducer
        self.name = name or reducer

    def aggregate(self, scores: list[float]) -> float:
        valid = [s for s in scores if not math.isnan(s)]
        if not valid:
            return float("nan")
        if self.reducer == "mean":
            return sum(valid) / len(valid)
        if self.reducer == "median":
            return statistics.median(valid)
        if self.reducer == "min":
            return min(valid)
        if self.reducer == "max":
            return max(valid)
        if self.reducer == "sum":
            return sum(valid)
        raise ValueError(f"unknown reducer: {self.reducer!r}")
