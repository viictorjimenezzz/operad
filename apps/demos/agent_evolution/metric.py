"""Deterministic offline metric for the agent_evolution showcase.

Scores a prediction's `.value` against a target mutation quality count.
Fitness rises as the seed accumulates useful rule, role, task, and config
changes up to `target`.
"""

from __future__ import annotations

from pydantic import BaseModel

from operad.metrics.metric import MetricBase


class RuleCountMetric(MetricBase):
    name = "rule_count"

    def __init__(self, target: int = 3) -> None:
        if target < 1:
            raise ValueError(f"target must be >= 1, got {target}")
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target
