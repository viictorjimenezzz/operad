"""The `Metric` protocol and default-batch base class."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class Metric(Protocol):
    """Anything that compares two Pydantic objects and returns a scalar.

    Higher is always better. Implementations may be pure-Python or may
    themselves be `Agent` instances (an LLM judge).
    """

    name: str

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float: ...

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]: ...


class MetricBase:
    """Default `Metric` implementation supplying a batch fan-out.

    Concrete metrics that do not need a custom batching strategy can
    inherit from this class and override only `score`. Metrics that can
    parallelise (e.g. LLM-judge metrics like `RubricCritic`) override
    `score_batch` directly.
    """

    name: str = ""

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        raise NotImplementedError

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        # Fan the per-row coroutines out so sync/CPU-bound scorers run
        # sequentially (their await is trivial) but async scorers that
        # suspend on I/O can overlap without each subclass having to
        # override this method.
        return list(await asyncio.gather(*(self.score(p, e) for p, e in pairs)))
