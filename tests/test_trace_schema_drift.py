"""Tests for `Trace.load` / `Trace.replay` output-schema drift detection."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.metrics import ExactMatch
from operad.runtime.observers import base as _obs
from operad.runtime.trace import Trace, TraceObserver
from operad.utils.errors import BuildError

from tests.conftest import A, FakeLeaf


pytestmark = pytest.mark.asyncio


class AnswerV1(BaseModel):
    answer: str = ""


class AnswerV2(BaseModel):
    answer: str = ""
    confidence: float = 0.0


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    _obs.registry.clear()
    yield
    _obs.registry.clear()


async def _capture_leaf_trace(cfg, tmp_path, output_cls):
    leaf = await FakeLeaf(
        config=cfg, input=A, output=output_cls, canned={"answer": "hi"}
    ).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await leaf(A(text="go"))
    finally:
        _obs.registry.clear()
    t = obs.last()
    assert t is not None
    path = tmp_path / "trace.json"
    t.save(path)
    return path, leaf


async def test_load_warns_on_drift(cfg, tmp_path) -> None:
    path, _ = await _capture_leaf_trace(cfg, tmp_path, AnswerV1)
    mutated = await FakeLeaf(config=cfg, input=A, output=AnswerV2).abuild()

    with pytest.warns(UserWarning, match="schema_drift"):
        Trace.load(path, agent=mutated)


async def test_load_without_agent_does_not_warn(cfg, tmp_path, recwarn) -> None:
    path, _ = await _capture_leaf_trace(cfg, tmp_path, AnswerV1)
    Trace.load(path)
    assert not [w for w in recwarn.list if "schema_drift" in str(w.message)]


async def test_replay_strict_raises_on_drift(cfg, tmp_path) -> None:
    path, _ = await _capture_leaf_trace(cfg, tmp_path, AnswerV1)
    mutated = await FakeLeaf(config=cfg, input=A, output=AnswerV2).abuild()
    trace = Trace.model_validate_json(path.read_text())

    with pytest.raises(BuildError) as excinfo:
        await trace.replay(mutated, [ExactMatch()])
    assert excinfo.value.reason == "schema_drift"


async def test_replay_non_strict_flags_report(cfg, tmp_path) -> None:
    path, _ = await _capture_leaf_trace(cfg, tmp_path, AnswerV1)
    mutated = await FakeLeaf(config=cfg, input=A, output=AnswerV2).abuild()
    trace = Trace.model_validate_json(path.read_text())

    with pytest.warns(UserWarning, match="schema_drift"):
        report = await trace.replay(
            mutated,
            [ExactMatch()],
            expected=AnswerV2(answer="hi"),
            predicted_cls=AnswerV2,
            strict=False,
        )
    assert report.summary["schema_drift"] == 1.0


async def test_composite_path_drift_names_changed_stage(cfg, tmp_path) -> None:
    captured_cfg = cfg

    class Chain(Agent):
        input = A
        output = AnswerV1

        def __init__(self, *, second_out: type[BaseModel]) -> None:
            super().__init__(config=None, input=A, output=second_out)
            self.first = FakeLeaf(
                config=captured_cfg, input=A, output=AnswerV1, canned={"answer": "a"}
            )
            self.second = FakeLeaf(
                config=captured_cfg,
                input=AnswerV1,
                output=second_out,
                canned={"answer": "b"},
            )

        async def forward(self, x: A) -> Any:
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    captured = await Chain(second_out=AnswerV1).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await captured(A(text="go"))
    finally:
        _obs.registry.clear()
    trace = obs.last()
    assert trace is not None

    from operad.runtime.trace import _collect_drift

    mutated = await Chain(second_out=AnswerV2).abuild()
    drift = _collect_drift(trace, mutated)
    drifted_paths = [d[0] for d in drift]
    assert "Chain.second" in drifted_paths
    assert "Chain.first" not in drifted_paths


async def test_no_drift_baseline_is_silent(cfg, tmp_path, recwarn) -> None:
    path, leaf = await _capture_leaf_trace(cfg, tmp_path, AnswerV1)
    Trace.load(path, agent=leaf)
    assert not [w for w in recwarn.list if "schema_drift" in str(w.message)]

    trace = Trace.model_validate_json(path.read_text())
    report = await trace.replay(
        leaf,
        [ExactMatch()],
        expected=AnswerV1(answer="hi"),
        predicted_cls=AnswerV1,
    )
    assert "schema_drift" not in report.summary
