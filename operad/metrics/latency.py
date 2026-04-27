"""Latency metric."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from .metric import MetricBase


@dataclass
class Latency(MetricBase):
    """Wall-clock time (seconds) of a callable, returned as a negative score."""

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


__all__ = ["Latency"]
