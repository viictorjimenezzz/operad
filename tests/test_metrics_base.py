"""`MetricBase` default + override semantics."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from operad import MetricBase

from .conftest import A


pytestmark = pytest.mark.asyncio


@dataclass
class _ScoreOnly(MetricBase):
    name: str = "score_only"

    async def score(self, predicted, expected) -> float:
        return 1.0 if predicted == expected else 0.0


@dataclass
class _BatchOverride(MetricBase):
    name: str = "batch_override"

    async def score(self, predicted, expected) -> float:
        return 0.0

    async def score_batch(self, pairs) -> list[float]:
        return [42.0 for _ in pairs]


async def test_default_score_batch_loops_score() -> None:
    pairs = [(A(text="x"), A(text="x")), (A(text="y"), A(text="z"))]
    scores = await _ScoreOnly().score_batch(pairs)
    assert scores == [1.0, 0.0]


async def test_override_wins_over_default() -> None:
    pairs = [(A(text="x"), A(text="x")), (A(text="y"), A(text="y"))]
    scores = await _BatchOverride().score_batch(pairs)
    assert scores == [42.0, 42.0]
