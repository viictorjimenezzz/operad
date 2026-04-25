"""Offline tests for `operad.optim.opro.OPROOptimizer`."""

from __future__ import annotations

from typing import Any

import pytest

import warnings

from operad.core.agent import _TRACER
from operad.metrics.base import MetricBase
from operad.optim import (
    OPROAgent,
    OPROInput,
    OPROOptimizer,
    OPROOutput,
    TextParameter,
)
from operad.optim.parameter import TextConstraint
from tests._helpers.fake_leaf import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class _DummyMetric(MetricBase):
    name = "dummy"

    async def score(self, predicted: Any, expected: Any) -> float:
        return 0.0


class StubOPROAgent(OPROAgent):
    """Returns pre-programmed candidates in order."""

    def __init__(self, *args: Any, canned: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._canned = list(canned or [])
        self.calls: list[OPROInput] = []

    async def forward(self, x: OPROInput) -> OPROOutput:  # type: ignore[override]
        if _TRACER.get() is not None:
            # During build() tracing: emit a sentinel without consuming canned.
            return OPROOutput(new_value="sentinel")
        self.calls.append(x)
        if not self._canned:
            return OPROOutput(new_value="fallback")
        return OPROOutput(new_value=self._canned.pop(0))


def _make_role_param(
    cfg: Any, initial: str = "initial"
) -> tuple[FakeLeaf, TextParameter]:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = initial
    return leaf, TextParameter.from_agent(leaf, "role", "role")


async def _built_opro(cfg: Any, canned: list[str]) -> StubOPROAgent:
    return await StubOPROAgent(config=cfg, canned=canned).abuild()


async def test_accepts_first_candidate_when_history_empty(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    opro = await _built_opro(cfg, ["cand-1"])
    scores = {"cand-1": 0.5}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
    )
    await opt.step()

    assert p.value == "cand-1"
    history = p.momentum_state["opro"]
    assert history == [("cand-1", 0.5)]


async def test_rejected_candidate_retries_and_keeps_current(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    # Prior history shows best score of 0.9; candidates must beat that.
    p.momentum_state["opro"] = [("past", 0.9)]
    opro = await _built_opro(cfg, ["low-1", "low-2", "low-3"])
    scores = {"low-1": 0.1, "low-2": 0.2, "low-3": 0.3}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
        max_retries=3,
    )
    await opt.step()

    assert p.value == "start"  # nothing beat 0.9 best
    history = p.momentum_state["opro"]
    assert history == [
        ("past", 0.9),
        ("low-1", 0.1),
        ("low-2", 0.2),
        ("low-3", 0.3),
    ]


async def test_accepts_first_candidate_that_beats_best(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    p.momentum_state["opro"] = [("past", 0.5)]
    opro = await _built_opro(cfg, ["low", "win"])
    scores = {"low": 0.2, "win": 0.9}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
        max_retries=3,
    )
    await opt.step()

    assert p.value == "win"
    history = p.momentum_state["opro"]
    assert history == [("past", 0.5), ("low", 0.2), ("win", 0.9)]
    # OPRO agent should have seen growing history across calls.
    assert len(opro.calls) == 2
    assert [h.value for h in opro.calls[0].history] == ["past"]
    assert [h.value for h in opro.calls[1].history] == ["past", "low"]


async def test_coerced_candidate_accepted_with_warning(cfg: Any) -> None:
    """Regression: exhausted retries on coerced candidates must warn and update."""
    leaf, p = _make_role_param(cfg, "start")
    # Constraint: max 3 chars — any candidate longer than that is coerced.
    p.constraint = TextConstraint(max_length=3)
    # All candidates will be longer than 3 chars and thus coerced.
    opro = await _built_opro(cfg, ["long-a", "long-b", "long-c"])
    # Coerced values: "lon", "lon", "lon" (first 3 chars).
    scores = {"lon": 0.7}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores.get(candidate, 0.0)

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
        max_retries=3,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await opt.step()

    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert any("coerced" in str(w.message).lower() for w in user_warnings)
    assert p.value == "lon"


async def test_history_truncates_to_k(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    p.momentum_state["opro"] = [(f"v{i}", float(i) / 10.0) for i in range(5)]

    opro = await _built_opro(cfg, ["new-1"])
    scores = {"new-1": 0.05}  # loses

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
        history_k=3,
        max_retries=1,
    )
    await opt.step()

    history = p.momentum_state["opro"]
    # 5 prior + 1 new = 6 total, truncated to history_k=3.
    assert [v for v, _ in history] == ["v3", "v4", "new-1"]
