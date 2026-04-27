"""Tests for LLMAAJ (LLM-judge-as-metric wrapper)."""

from __future__ import annotations

import asyncio

import pytest

from operad import Metric
from operad.agents.reasoning.schemas import Candidate, Score
from operad.metrics import LLMAAJ

from ..conftest import A, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_llmaaj_score_returns_score_field(cfg) -> None:
    critic = FakeLeaf(
        config=cfg,
        input=Candidate,
        output=Score,
        canned={"score": 0.7, "rationale": "ok"},
    )
    await critic.abuild()
    m = LLMAAJ(judge=critic)
    assert await m.score(A(text="anything"), A(text="anything")) == 0.7


async def test_llmaaj_score_batch_preserves_order(cfg) -> None:
    critic = FakeLeaf(
        config=cfg,
        input=Candidate,
        output=Score,
        canned={"score": 0.5, "rationale": ""},
    )
    await critic.abuild()
    m = LLMAAJ(judge=critic)
    pairs = [(A(text=str(i)), A(text="")) for i in range(4)]
    scores = await m.score_batch(pairs)
    assert scores == [0.5, 0.5, 0.5, 0.5]


async def test_llmaaj_score_batch_runs_concurrently(cfg) -> None:
    """Batch fans out concurrently — proven by a shared inflight counter."""
    inflight = 0
    max_inflight = 0

    class SlowCritic(FakeLeaf):
        async def forward(self, x):  # type: ignore[override]
            nonlocal inflight, max_inflight
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.01)
            inflight -= 1
            return self.output.model_construct(**self.canned)

    critic = SlowCritic(
        config=cfg,
        input=Candidate,
        output=Score,
        canned={"score": 0.9, "rationale": ""},
    )
    await critic.abuild()
    m = LLMAAJ(judge=critic)
    pairs = [(A(text=str(i)), A(text="")) for i in range(4)]
    await m.score_batch(pairs)
    assert max_inflight >= 2


async def test_llmaaj_is_runtime_checkable(cfg) -> None:
    critic = FakeLeaf(
        config=cfg, input=Candidate, output=Score, canned={"score": 0.1},
    )
    await critic.abuild()
    assert isinstance(LLMAAJ(judge=critic), Metric)
