"""Wrap an `Agent[Candidate, Score]` (an LLM judge) as a `Metric`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..agents.reasoning.schemas import Candidate
from ..core.agent import Agent
from .base import MetricBase


@dataclass
class RubricCritic(MetricBase):
    """Expose a critic agent as a `Metric`.

    `.score()` builds a `Candidate(output=predicted)` and returns the
    critic's `Score.score`. `.score_batch` fans out with `asyncio.gather`
    so evaluation parallelises correctly — the slot registry throttles
    the underlying backend, not this gather.

    The critic is not given the original request because `Metric.score`'s
    signature is `(predicted, expected)`; judges configured for this
    wrapper should rate outputs on their own merits (e.g. "score this
    answer's clarity") rather than requiring the request.
    """

    critic: Agent[Any, Any]
    name: str = "rubric"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        out = await self.critic(Candidate(output=predicted))
        return float(out.response.score)

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        results = await asyncio.gather(
            *(self.critic(Candidate(output=p)) for p, _ in pairs)
        )
        return [float(r.response.score) for r in results]
