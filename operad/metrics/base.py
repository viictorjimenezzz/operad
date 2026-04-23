"""The `Metric` protocol."""

from __future__ import annotations

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
