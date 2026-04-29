"""Offline tests for `operad.optim.optimizers.opro.OPROOptimizer`."""

from __future__ import annotations

from typing import Any

import pytest

from operad.core.agent import _TRACER
from operad.metrics.metric import MetricBase
from operad.optim.optimizers.opro import (
    OPROAgent,
    OPROInput,
    OPROOptimizer,
    OPROOutput,
)
from operad.optim.parameter import TextParameter
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import registry as obs_registry
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
    _leaf, p = _make_role_param(cfg, "start")
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


async def test_opro_session_emits_algorithm_events(cfg: Any) -> None:
    _leaf, p = _make_role_param(cfg, "start")
    opro = await _built_opro(cfg, ["cand-1"])
    events: list[AlgorithmEvent] = []

    class _Collector:
        async def on_event(self, event: object) -> None:
            if isinstance(event, AlgorithmEvent):
                events.append(event)

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return 0.8

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
    )
    obs_registry.clear()
    obs_registry.register(_Collector())
    try:
        async with opt.session():
            await opt.step()
    finally:
        obs_registry.clear()

    kinds = [event.kind for event in events]
    assert kinds == ["algo_start", "iteration", "iteration", "algo_end"]
    assert events[1].payload["phase"] == "propose"
    assert events[1].payload["current_value"] == "start"
    assert events[2].payload["phase"] == "evaluate"
    assert events[2].payload["accepted"] is True
    assert len({event.run_id for event in events}) == 1
    assert events[-1].payload["final_values"] == {"role": "cand-1"}


async def test_opro_empty_session_does_not_emit_algorithm_run(cfg: Any) -> None:
    _leaf, p = _make_role_param(cfg, "start")
    opro = await _built_opro(cfg, [])
    events: list[AlgorithmEvent] = []

    class _Collector:
        async def on_event(self, event: object) -> None:
            if isinstance(event, AlgorithmEvent):
                events.append(event)

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return 0.0

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
    )
    obs_registry.clear()
    obs_registry.register(_Collector())
    try:
        async with opt.session():
            pass
    finally:
        obs_registry.clear()

    assert events == []


async def test_opro_standalone_steps_share_one_algorithm_run(cfg: Any) -> None:
    _leaf, p = _make_role_param(cfg, "start")
    opro = await _built_opro(cfg, ["cand-1", "cand-2"])
    events: list[AlgorithmEvent] = []

    class _Collector:
        async def on_event(self, event: object) -> None:
            if isinstance(event, AlgorithmEvent):
                events.append(event)

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return {"cand-1": 0.8, "cand-2": 0.9}[candidate]

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
    )
    obs_registry.clear()
    obs_registry.register(_Collector())
    try:
        await opt.step()
        await opt.step()
        async with opt.session():
            pass
    finally:
        obs_registry.clear()

    kinds = [event.kind for event in events]
    assert kinds == [
        "algo_start",
        "iteration",
        "iteration",
        "iteration",
        "iteration",
        "algo_end",
    ]
    assert len({event.run_id for event in events}) == 1
    assert [event.payload.get("step_index") for event in events[1:5]] == [1, 1, 2, 2]
    assert events[-1].payload["steps"] == 2
    assert events[-1].payload["final_values"] == {"role": "cand-2"}


async def test_opro_evaluator_can_emit_tracking_metrics(cfg: Any) -> None:
    _leaf, p = _make_role_param(cfg, "start")
    opro = await _built_opro(cfg, ["cand-1"])
    events: list[AlgorithmEvent] = []

    class _Collector:
        async def on_event(self, event: object) -> None:
            if isinstance(event, AlgorithmEvent):
                events.append(event)

    async def evaluator(param: TextParameter, candidate: str) -> tuple[float, dict[str, float]]:
        return 0.8, {"length_mean": 240, "length_max": 301}

    opt = OPROOptimizer(
        [p],
        objective_metric=_DummyMetric(),
        evaluator=evaluator,
        opro_factory=lambda: opro,
    )
    obs_registry.clear()
    obs_registry.register(_Collector())
    try:
        await opt.step()
    finally:
        obs_registry.clear()

    evaluate_event = next(event for event in events if event.payload.get("phase") == "evaluate")
    assert evaluate_event.payload["metrics"] == {"length_mean": 240.0, "length_max": 301.0}
