"""Tests for `operad.BestOfN`: plain algorithm (non-Agent) with `run(x)`."""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent
from operad.algorithms import BestOfN, Candidate, Score

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


class _Counter(Agent[A, B]):
    """Leaf variant that mints a different canned output per call."""

    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=B)
        self.calls = 0

    async def forward(self, x: A) -> B:  # type: ignore[override]
        self.calls += 1
        return B.model_construct(value=self.calls * 10)


class _ScoreByCandidate(Agent[Candidate, Score]):
    """Judge that scores candidates equal to their `output.value`.

    Trace-safe: during the sentinel trace `Candidate.output` is None.
    """

    input = Candidate
    output = Score

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0) if x.output is not None else 0
        return Score(score=float(value), rationale=f"v={value}")


async def test_best_of_n_picks_highest_scoring_candidate(cfg) -> None:
    generator = await _Counter(cfg).abuild()
    judge = await _ScoreByCandidate(config=cfg).abuild()
    generator.calls = 0  # build()'s sentinel trace already bumped it

    bon = BestOfN(generator=generator, judge=judge, n=4)
    out = await bon.run(A(text="go"))

    assert isinstance(out, B)
    # _Counter emits 10, 20, 30, 40 across four calls; highest wins.
    assert out.value == 40


async def test_best_of_n_rejects_zero_n(cfg) -> None:
    generator = _Counter(cfg)
    judge = _ScoreByCandidate(config=cfg)
    with pytest.raises(ValueError, match="n must be >= 1"):
        BestOfN(generator=generator, judge=judge, n=0)


async def test_best_of_n_is_not_an_agent(cfg) -> None:
    """Taxonomy invariant: algorithms are plain classes, not Agents."""
    generator = _Counter(cfg)
    judge = _ScoreByCandidate(config=cfg)
    bon = BestOfN(generator=generator, judge=judge, n=2)
    assert not isinstance(bon, Agent)


async def test_best_of_n_requires_children_to_be_built(cfg) -> None:
    """`BestOfN` doesn't build generator/judge itself; caller does."""
    generator = _Counter(cfg)
    judge = _ScoreByCandidate(config=cfg)
    bon = BestOfN(generator=generator, judge=judge, n=2)
    from operad import BuildError

    with pytest.raises(BuildError) as exc:
        await bon.run(A(text="go"))
    assert exc.value.reason == "not_built"
