"""Deterministic metrics that never touch an LLM."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import MetricBase

T = TypeVar("T", bound=BaseModel)


@dataclass
class ExactMatch(MetricBase):
    """1.0 if `predicted == expected` (deep Pydantic equality), else 0.0."""

    name: str = "exact_match"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return 1.0 if predicted == expected else 0.0


@dataclass
class JsonValid(MetricBase):
    """1.0 if `predicted` round-trips through `model_dump_json` cleanly.

    Pydantic v2 objects are validated at construction, so this almost
    always returns 1.0 — it's useful as a guard for classes whose
    validators run lazily, or for `model_construct`ed instances.
    """

    name: str = "json_valid"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        try:
            dumped = predicted.model_dump_json()
            type(predicted).model_validate_json(dumped)
        except Exception:
            return 0.0
        return 1.0


@dataclass
class Latency(MetricBase):
    """Wall-clock time (seconds) of a callable, returned as a *negative* score.

    Metrics are "higher is better" by convention. Call
    `await Latency().measure(fn, *args)` to record an elapsed time; it
    returns `-elapsed` so the fastest run wins on the raw scale.

    `score()` reports a normalised `1 / (1 + latest_measurement)` in
    `(0.0, 1.0]` based on the most recent `measure()`; returns `0.0`
    when nothing has been measured yet. Pair the two: `measure` captures,
    `score` summarises.
    """

    name: str = "latency"
    _measurements: list[float] = field(default_factory=list)

    async def measure(
        self,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> float:
        start = time.perf_counter()
        await fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        self._measurements.append(elapsed)
        return -elapsed

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del predicted, expected
        if not self._measurements:
            return 0.0
        return 1.0 / (1.0 + self._measurements[-1])
