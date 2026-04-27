"""Tests for `operad.benchmark.regression_check`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from operad.benchmark import (
    Dataset,
    Entry,
    RegressionReport,
    regression_check,
)
from operad.metrics.metric import MetricBase
from operad.metrics.metric import ExactMatch
from operad.runtime.observers import base as _obs
from operad.runtime.trace import TraceObserver

from tests.conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    _obs.registry.clear()
    yield
    _obs.registry.clear()


async def _capture(agent: Any, x: BaseModel) -> Any:
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await agent(x)
    finally:
        _obs.registry.unregister(obs)
    return obs.last()


@dataclass
class AlwaysPass(MetricBase):
    name: str = "always_pass"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del predicted, expected
        return 1.0


# --- Trace mode ------------------------------------------------------------


async def test_trace_mode_no_drift(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()
    gold = await _capture(leaf, A(text="hi"))

    report = await regression_check(leaf, gold)

    assert isinstance(report, RegressionReport)
    assert report.ok is True
    assert report.mode == "trace"
    assert report.trace_diff is not None
    assert report.trace_diff.graphs_match


async def test_trace_mode_response_drift_fails_hash(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()
    gold = await _capture(leaf, A(text="hi"))

    # Mutate canned so the replay returns a different response_dump.
    leaf.canned = {"value": 42}

    report = await regression_check(leaf, gold)  # default equivalence="hash"

    assert report.ok is False
    assert report.mode == "trace"


async def test_trace_mode_metric_equivalence_tolerates_surface(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()
    gold = await _capture(leaf, A(text="hi"))

    leaf.canned = {"value": 999}  # response differs; AlwaysPass scores 1.0

    report = await regression_check(
        leaf,
        gold,
        metrics=[AlwaysPass()],
        equivalence="metric",
        threshold=1.0,
    )

    assert report.ok is True
    assert report.threshold == 1.0


async def test_trace_mode_exact_equivalence_flags_any_change(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()
    gold = await _capture(leaf, A(text="hi"))

    leaf.canned = {"value": 8}

    report = await regression_check(leaf, gold, equivalence="exact")
    assert report.ok is False


async def test_gold_as_path(cfg, tmp_path) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 3}
    ).abuild()
    gold = await _capture(leaf, A(text="rt"))
    path = tmp_path / "gold.json"
    gold.save(path)

    report = await regression_check(leaf, path)
    assert report.ok is True
    assert report.mode == "trace"


async def test_agent_hash_content_recorded(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    gold = await _capture(leaf, A(text="h"))

    report = await regression_check(leaf, gold)
    assert report.agent_hash_content == leaf.hash_content


# --- Dataset mode ----------------------------------------------------------


async def test_dataset_mode_passing(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 5}
    ).abuild()
    ds = Dataset(
        [
            Entry(input=A(text="a"), expected_output=B(value=5)),
            Entry(input=A(text="b"), expected_output=B(value=5)),
            Entry(input=A(text="c"), expected_output=B(value=5)),
        ]
    )

    report = await regression_check(
        leaf, ds, metrics=[ExactMatch()], threshold=1.0
    )
    assert report.ok is True
    assert report.mode == "dataset"
    assert report.actual == 1.0


async def test_dataset_mode_failing(cfg) -> None:
    # Leaf always returns value=5 but only 2 of 3 expected outputs match.
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 5}
    ).abuild()
    ds = Dataset(
        [
            Entry(input=A(text="a"), expected_output=B(value=5)),
            Entry(input=A(text="b"), expected_output=B(value=5)),
            Entry(input=A(text="c"), expected_output=B(value=9)),
        ]
    )

    report = await regression_check(
        leaf, ds, metrics=[ExactMatch()], threshold=1.0
    )
    assert report.ok is False
    assert report.actual is not None
    assert abs(report.actual - (2 / 3)) < 1e-9


# --- Errors ----------------------------------------------------------------


async def test_dataset_with_hash_equivalence_raises(cfg) -> None:
    ds: Dataset[Any, Any] = Dataset([Entry(input=A(text="x"), expected_output=B(value=1))])
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    with pytest.raises(ValueError, match="trace-only"):
        await regression_check(
            leaf, ds, metrics=[ExactMatch()], equivalence="hash"
        )


async def test_dataset_mode_requires_metrics(cfg) -> None:
    ds: Dataset[Any, Any] = Dataset([Entry(input=A(text="x"), expected_output=B(value=1))])
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    with pytest.raises(ValueError, match="metrics"):
        await regression_check(leaf, ds)


async def test_dataset_entry_missing_expected_output_raises(cfg) -> None:
    ds: Dataset[Any, Any] = Dataset([Entry(input=A(text="x"))])
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    with pytest.raises(ValueError, match="expected_output"):
        await regression_check(leaf, ds, metrics=[ExactMatch()])


async def test_unknown_gold_type_raises(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    with pytest.raises(ValueError):
        await regression_check(leaf, 42)  # type: ignore[arg-type]


async def test_metric_equivalence_requires_metrics(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    gold = await _capture(leaf, A(text="x"))
    with pytest.raises(ValueError, match="metric"):
        await regression_check(leaf, gold, equivalence="metric")
