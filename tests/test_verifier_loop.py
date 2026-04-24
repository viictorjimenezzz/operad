"""Tests for `operad.VerifierLoop`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.algorithms import Candidate, Score, VerifierLoop

from .conftest import A, B


pytestmark = pytest.mark.asyncio


class _Counter(Agent[A, B]):
    """Leaf that mints `B(value=calls*10)` per call."""

    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=B)
        self.calls = 0

    async def forward(self, x: A) -> B:  # type: ignore[override]
        self.calls += 1
        return B.model_construct(value=self.calls * 10)


class _ThresholdCritic(Agent[Candidate, Score]):
    """Critic that scores 1.0 iff candidate.value >= threshold, else 0.0."""

    input = Candidate
    output = Score

    def __init__(self, cfg, threshold: int) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)
        self.threshold = threshold

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0) if x.output is not None else 0
        return Score(score=1.0 if value >= self.threshold else 0.0)


async def test_verifier_loop_exits_early_on_threshold(cfg) -> None:
    gen = await _Counter(cfg).abuild()
    critic = await _ThresholdCritic(cfg, threshold=20).abuild()
    gen.calls = 0

    loop = VerifierLoop(gen, critic, threshold=0.8, max_iter=5)
    out = await loop.run(A(text="q"))
    assert out.value == 20
    assert gen.calls == 2


async def test_verifier_loop_returns_last_after_max_iter(cfg) -> None:
    gen = await _Counter(cfg).abuild()
    critic = await _ThresholdCritic(cfg, threshold=10_000).abuild()
    gen.calls = 0

    loop = VerifierLoop(gen, critic, threshold=0.8, max_iter=3)
    out = await loop.run(A(text="q"))
    assert out.value == 30
    assert gen.calls == 3


async def test_verifier_loop_rejects_zero_max_iter(cfg) -> None:
    gen = _Counter(cfg)
    critic = _ThresholdCritic(cfg, threshold=0)
    with pytest.raises(ValueError, match="max_iter"):
        VerifierLoop(gen, critic, max_iter=0)
