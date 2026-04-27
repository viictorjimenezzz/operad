"""Metric protocol, batch base class, and simple schema metrics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class Metric(Protocol):
    """Anything that compares two Pydantic objects and returns a scalar."""

    name: str

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float: ...

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]: ...


class MetricBase:
    """Default `Metric` implementation supplying a batch fan-out."""

    name: str = ""

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        raise NotImplementedError

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        return list(await asyncio.gather(*(self.score(p, e) for p, e in pairs)))


@dataclass
class ExactMatch(MetricBase):
    """1.0 if `predicted == expected` (deep Pydantic equality), else 0.0."""

    name: str = "exact_match"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return 1.0 if predicted == expected else 0.0


@dataclass
class JsonValid(MetricBase):
    """1.0 if `predicted` round-trips through its schema cleanly."""

    name: str = "json_valid"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        try:
            dumped = predicted.model_dump_json()
            type(predicted).model_validate_json(dumped)
        except Exception:
            return 0.0
        return 1.0


__all__ = ["ExactMatch", "JsonValid", "Metric", "MetricBase"]
