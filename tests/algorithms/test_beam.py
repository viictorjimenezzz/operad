"""Tests for `operad.Beam`: plain algorithm (non-Agent) with `run(x)`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.agents.reasoning.schemas import Candidate, Score
from operad.algorithms import Beam

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


_SHARED_COUNTER: list[int] = [0]


class _Counter(Agent[A, B]):
    """Leaf variant that mints a different canned output per call.

    Uses a module-level counter so clones and original share the
    sequence — necessary for Beam tests where ``n`` independent clones
    each sample one output. Skips the bump when a symbolic tracer is
    active so repeated ``abuild()`` calls do not pollute the counter.
    """

    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=B)

    async def forward(self, x: A) -> B:  # type: ignore[override]
        from operad.core.agent import _TRACER

        if _TRACER.get() is not None:
            return B.model_construct(value=0)
        _SHARED_COUNTER[0] += 1
        return B.model_construct(value=_SHARED_COUNTER[0] * 10)


class _ScoreByCandidate(Agent[Candidate, Score]):
    """Judge that scores candidates equal to their `output.value`.

    Trace-safe: during the sentinel trace `Candidate.output` is None.
    """

    input = Candidate
    output = Score

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0) if x.output is not None else 0
        return Score(score=float(value), rationale=f"v={value}")


async def _make_beam(cfg, **kwargs) -> Beam:
    """Construct a Beam with test-specific generator/judge overrides.

    Beam's class-level defaults are production components; tests
    swap them for deterministic leaves via instance-attr overwrite.
    """
    beam = Beam(**kwargs)
    beam.generator = await _Counter(cfg).abuild()
    beam.judge = await _ScoreByCandidate(config=cfg).abuild()
    return beam


async def test_beam_picks_highest_scoring_candidate(cfg) -> None:
    beam = await _make_beam(cfg, n=4)
    _SHARED_COUNTER[0] = 0
    outs = await beam.run(A(text="go"))

    assert isinstance(outs, list)
    assert len(outs) == 4
    assert all(isinstance(o, B) for o in outs)
    # top_k defaults to n, so all candidates are returned in ranked order.
    assert [o.value for o in outs] == [40, 30, 20, 10]


async def test_beam_top_k_returns_multiple(cfg) -> None:
    beam = await _make_beam(cfg, n=4, top_k=2)
    _SHARED_COUNTER[0] = 0
    outs = await beam.run(A(text="go"))
    assert len(outs) == 2
    assert [o.value for o in outs] == [40, 30]


async def test_beam_without_judge_keeps_generation_order(cfg) -> None:
    beam = await _make_beam(cfg, n=4, top_k=2)
    beam.judge = None
    _SHARED_COUNTER[0] = 0
    outs = await beam.run(A(text="go"))
    assert [o.value for o in outs] == [10, 20]


async def test_beam_rejects_zero_n() -> None:
    with pytest.raises(ValueError, match="n must be >= 1"):
        Beam(n=0)


async def test_beam_rejects_top_k_larger_than_n() -> None:
    with pytest.raises(ValueError, match="top_k"):
        Beam(n=2, top_k=3)


class _Scored(BaseModel):
    value: int = 0
    score: float | None = None


class _CounterScored(Agent[A, _Scored]):
    input = A
    output = _Scored

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=_Scored)

    async def forward(self, x: A) -> _Scored:  # type: ignore[override]
        from operad.core.agent import _TRACER

        if _TRACER.get() is not None:
            return _Scored.model_construct(value=0, score=None)
        _SHARED_COUNTER[0] += 1
        return _Scored.model_construct(value=_SHARED_COUNTER[0] * 10, score=None)


async def test_beam_injects_score_when_output_declares_score(cfg) -> None:
    beam: Beam[A, _Scored] = Beam(n=3, top_k=2)
    beam.generator = await _CounterScored(cfg).abuild()
    beam.judge = await _ScoreByCandidate(config=cfg).abuild()
    _SHARED_COUNTER[0] = 0
    outs = await beam.run(A(text="go"))
    assert [o.value for o in outs] == [30, 20]
    assert [o.score for o in outs] == [30.0, 20.0]


async def test_beam_is_not_an_agent() -> None:
    """Taxonomy invariant: algorithms are plain classes, not Agents."""
    assert not isinstance(Beam(n=2), Agent)
