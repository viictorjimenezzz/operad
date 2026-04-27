"""Wrap an `Agent[Candidate, Score]` judge as a `Metric`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..agents.reasoning.schemas import Candidate
from ..core.agent import Agent
from .metric import MetricBase


@dataclass
class LLMAAJ(MetricBase):
    """Expose a judge agent as a metric."""

    judge: Agent[Any, Any]
    name: str = "llmaaj"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        out = await self.judge(Candidate(output=predicted))
        return float(out.response.score)

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        results = await asyncio.gather(
            *(self.judge(Candidate(output=p)) for p, _ in pairs)
        )
        return [float(r.response.score) for r in results]


__all__ = ["LLMAAJ"]
