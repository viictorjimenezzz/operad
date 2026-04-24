"""Tests for `operad.VerifierLoop`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents.reasoning.schemas import Candidate, Score
from operad.algorithms import VerifierLoop

from ..conftest import A, B


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


async def _make_loop(cfg, *, critic_threshold: int, **kwargs) -> VerifierLoop:
    """Build a VerifierLoop with test generator/critic swapped in."""
    loop = VerifierLoop(**kwargs)
    loop.generator = await _Counter(cfg).abuild()
    loop.generator.calls = 0
    loop.critic = await _ThresholdCritic(cfg, threshold=critic_threshold).abuild()
    return loop


async def test_verifier_loop_exits_early_on_threshold(cfg) -> None:
    loop = await _make_loop(cfg, critic_threshold=20, max_iter=5)
    out = await loop.run(A(text="q"))
    assert out.value == 20
    assert loop.generator.calls == 2


async def test_verifier_loop_returns_last_after_max_iter(cfg) -> None:
    loop = await _make_loop(cfg, critic_threshold=10_000, max_iter=3)
    out = await loop.run(A(text="q"))
    assert out.value == 30
    assert loop.generator.calls == 3


async def test_verifier_loop_rejects_zero_max_iter() -> None:
    with pytest.raises(ValueError, match="max_iter"):
        VerifierLoop(max_iter=0)
