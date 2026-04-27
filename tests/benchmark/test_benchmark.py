"""Tests for the `operad.benchmark` package."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path

import pytest
from pydantic import BaseModel

from operad import BuildError, Dataset, evaluate
from operad.benchmark import AggregatedMetric, Entry, EvalReport
from operad.core.agent import _compute_graph_hash
from operad.metrics import ExactMatch, RegexMetric

from ..conftest import A, B, FakeLeaf


# --- Entry NDJSON round-trip ------------------------------------------------


def test_entry_ndjson_round_trip(tmp_path: Path) -> None:
    entries = [
        Entry(input=A(text="q1"), expected_output=A(text="hello")),
        Entry(input=A(text="q2"), expected_output=None),
        Entry(input=A(text="q3"), expected_output=A(text="hi"), metric=ExactMatch()),
    ]
    ds = Dataset(entries, name="t", version="v1")
    path = tmp_path / "d.ndjson"
    ds.save(path)

    loaded = Dataset.load(path, in_cls=A, out_cls=A, name="t", version="v1")
    rows = list(loaded)
    assert len(rows) == 3
    assert rows[0].input == A(text="q1")
    assert rows[0].expected_output == A(text="hello")
    assert rows[0].metric is None
    assert rows[1].expected_output is None
    assert rows[2].metric is None  # no registry → None

    # With a registry, metric rehydrates.
    em = ExactMatch()
    loaded2 = Dataset.load(
        path, in_cls=A, out_cls=A, metric_registry={em.name: em}
    )
    assert loaded2[2].metric is em


def test_load_missing_metric_key_raises(tmp_path: Path) -> None:
    ds = Dataset(
        [Entry(input=A(text="x"), expected_output=A(text="y"), metric=ExactMatch())],
    )
    path = tmp_path / "d.ndjson"
    ds.save(path)
    with pytest.raises(KeyError):
        Dataset.load(path, in_cls=A, out_cls=A, metric_registry={})


# --- Dataset hash stability + sensitivity -----------------------------------


def _base_entries() -> list[Entry[A, B]]:
    return [
        Entry(input=A(text="q1"), expected_output=B(value=1)),
        Entry(input=A(text="q2"), expected_output=B(value=2)),
    ]


def test_hash_stable_across_reconstruction() -> None:
    a = Dataset(_base_entries(), name="t", version="v1")
    b = Dataset(_base_entries(), name="t", version="v1")
    assert a.hash_dataset == b.hash_dataset


def test_hash_sensitive_to_fields() -> None:
    base = Dataset(_base_entries(), name="t", version="v1").hash_dataset
    assert Dataset(_base_entries(), name="t", version="v2").hash_dataset != base
    assert Dataset(_base_entries(), name="other", version="v1").hash_dataset != base

    mutated = _base_entries()
    mutated[0] = Entry(input=A(text="qX"), expected_output=B(value=1))
    assert Dataset(mutated, name="t", version="v1").hash_dataset != base


def test_hash_sensitive_to_per_entry_metric() -> None:
    base = Dataset(_base_entries(), name="t", version="v1").hash_dataset
    with_metric = _base_entries()
    with_metric[0] = Entry(
        input=A(text="q1"), expected_output=B(value=1), metric=ExactMatch()
    )
    assert Dataset(with_metric, name="t", version="v1").hash_dataset != base


# --- Tuple-compat constructor -----------------------------------------------


def test_construct_from_tuples() -> None:
    ds = Dataset(
        [(A(text="q1"), B(value=1)), (A(text="q2"), B(value=2))],
        name="t",
        version="v1",
    )
    assert len(ds) == 2
    assert ds[0].input == A(text="q1")
    assert ds[0].expected_output == B(value=1)


# --- runtime schema validation (M-4) ----------------------------------------


def test_dataset_in_out_cls_validates_cleanly() -> None:
    ds = Dataset(
        [(A(text="q1"), A(text="y1")), (A(text="q2"), A(text="y2"))],
        in_cls=A,
        out_cls=A,
    )
    assert len(ds) == 2


def test_dataset_in_out_cls_rejects_bad_rows() -> None:
    with pytest.raises(ValueError, match="row 0"):
        Dataset([("bad", "row")], in_cls=A, out_cls=A)


def test_dataset_in_out_cls_reports_index_of_bad_row() -> None:
    good = (A(text="ok"), A(text="ok"))
    with pytest.raises(ValueError, match="row 1"):
        Dataset([good, ("bad", "row")], in_cls=A, out_cls=A)


def test_dataset_without_cls_still_constructs_tuples() -> None:
    # Backwards-compat: omitting in_cls/out_cls preserves the prior path.
    ds = Dataset([(A(text="q"), B(value=1))])
    assert len(ds) == 1
    assert ds[0].input == A(text="q")


# --- evaluate with per-entry metrics ----------------------------------------


async def test_evaluate_per_entry_metrics(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "hello"})
    await agent.abuild()

    ds = Dataset(
        [
            Entry(
                input=A(text="q1"),
                expected_output=A(text="hello"),
                metric=ExactMatch(),
            ),
            Entry(
                input=A(text="q2"),
                expected_output=A(text="other"),
                metric=ExactMatch(),
            ),
            Entry(
                input=A(text="q3"),
                expected_output=A(text="ell"),
                metric=RegexMetric(field="text", mode="contains"),
            ),
        ],
    )
    report = await evaluate(agent, ds)

    assert isinstance(report, EvalReport)
    assert len(report.rows) == 3
    assert report.rows[0]["exact_match"] == 1.0
    assert report.rows[0]["metric"] == "exact_match"
    assert report.rows[1]["exact_match"] == 0.0
    assert report.rows[2]["regex_contains"] == 1.0
    assert report.rows[2]["metric"] == "regex_contains"
    assert set(report.summary.keys()) == {"exact_match", "regex_contains"}


# --- evaluate global-override ----------------------------------------------


async def test_evaluate_global_override_ignores_entry_metric(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "hello"})
    await agent.abuild()

    ds = Dataset(
        [
            Entry(
                input=A(text="q1"),
                expected_output=A(text="hello"),
                metric=RegexMetric(field="text", mode="contains"),
            ),
            Entry(
                input=A(text="q2"),
                expected_output=A(text="hello"),
                metric=RegexMetric(field="text", mode="contains"),
            ),
        ],
    )
    report = await evaluate(agent, ds, [ExactMatch()])

    assert all("exact_match" in row for row in report.rows)
    assert all("contains" not in row for row in report.rows)
    assert all("metric" not in row for row in report.rows)
    assert report.summary == {"exact_match": pytest.approx(1.0)}


# --- Parity with pre-refactor behaviour -------------------------------------


async def test_evaluate_happy_path_tuples(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "hello"})
    await agent.abuild()

    dataset = [
        (A(text="q1"), A(text="hello")),
        (A(text="q2"), A(text="hello")),
        (A(text="q3"), A(text="other")),
    ]
    report = await evaluate(agent, dataset, [ExactMatch()])
    assert report.summary["exact_match"] == pytest.approx(2 / 3)
    assert report.rows[0]["exact_match"] == 1.0
    assert report.rows[2]["exact_match"] == 0.0


async def test_evaluate_raises_when_not_built(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "x"})
    with pytest.raises(BuildError) as exc:
        await evaluate(agent, [(A(), A())], [ExactMatch()])
    assert exc.value.reason == "not_built"


async def test_evaluate_captures_row_errors_without_tanking_run(cfg) -> None:
    # A leaf that raises on the poisoned input but succeeds elsewhere.
    class FlakyLeaf(FakeLeaf):
        async def forward(self, x):  # type: ignore[override]
            if x.text == "poison":
                raise RuntimeError("simulated failure")
            return self.output.model_construct(**self.canned)

    agent = FlakyLeaf(config=cfg, input=A, output=A, canned={"text": "hello"})
    await agent.abuild()

    dataset = [
        (A(text="q1"), A(text="hello")),
        (A(text="poison"), A(text="hello")),
        (A(text="q3"), A(text="hello")),
    ]
    report = await evaluate(agent, dataset, [ExactMatch()])

    assert len(report.rows) == 3
    assert report.rows[0]["predicted"] == {"text": "hello"}
    assert report.rows[0]["exact_match"] == 1.0
    assert report.rows[1]["predicted"] is None
    assert report.rows[1]["error"]["type"] == "RuntimeError"
    assert "simulated failure" in report.rows[1]["error"]["message"]
    assert "exact_match" not in report.rows[1]
    assert report.rows[2]["predicted"] == {"text": "hello"}
    assert report.rows[2]["exact_match"] == 1.0
    # Summary is computed over successful rows only.
    assert report.summary["exact_match"] == pytest.approx(1.0)
    assert len(report.row_errors) == 1
    assert report.row_errors[0]["index"] == 1
    assert report.row_errors[0]["type"] == "RuntimeError"


async def test_evaluate_respects_concurrency_bound(cfg) -> None:
    inflight = 0
    max_inflight = 0

    class SlowLeaf(FakeLeaf):
        async def forward(self, x):  # type: ignore[override]
            nonlocal inflight, max_inflight
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1
            return self.output.model_construct(**self.canned)

    agent = SlowLeaf(config=cfg, input=A, output=A, canned={"text": "hi"})
    await agent.abuild()

    dataset = [(A(text=str(i)), A(text="hi")) for i in range(8)]
    await evaluate(agent, dataset, [ExactMatch()], concurrency=2)
    assert max_inflight <= 2
    assert max_inflight >= 1


async def test_evaluate_populates_hashes(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "hello"})
    await agent.abuild()

    ds = Dataset(
        [(A(text="q1"), A(text="hello")), (A(text="q2"), A(text="hello"))],
        name="greetings",
        version="v1",
    )
    report = await evaluate(agent, ds, [ExactMatch()])

    assert report.hash_dataset == ds.hash_dataset
    assert report.hash_dataset != ""
    assert report.hash_graph == _compute_graph_hash(agent)
    assert report.dataset_name == "greetings"
    assert report.dataset_version == "v1"


# --- AggregatedMetric reducers ----------------------------------------------


def test_aggregated_metric_reducers() -> None:
    assert AggregatedMetric(reducer="mean").aggregate([0.0, 1.0, 0.5]) == pytest.approx(0.5)
    assert AggregatedMetric(reducer="median").aggregate([0.0, 1.0, 0.5]) == 0.5
    assert AggregatedMetric(reducer="min").aggregate([0.0, 1.0, 0.5]) == 0.0
    assert AggregatedMetric(reducer="max").aggregate([0.0, 1.0, 0.5]) == 1.0
    assert AggregatedMetric(reducer="sum").aggregate([0.0, 1.0, 0.5]) == pytest.approx(1.5)


def test_aggregated_metric_nan_handling() -> None:
    m = AggregatedMetric(reducer="mean")
    assert m.aggregate([0.0, float("nan"), 1.0]) == pytest.approx(0.5)
    assert math.isnan(m.aggregate([float("nan"), float("nan")]))
    assert math.isnan(m.aggregate([]))


def test_aggregated_metric_default_name() -> None:
    assert AggregatedMetric(reducer="median").name == "median"
    assert AggregatedMetric(reducer="mean", name="pass_rate").name == "pass_rate"


# --- Top-level import surface -----------------------------------------------


def test_top_level_imports() -> None:
    from operad import Dataset as D, evaluate as ev  # noqa: F401
    from operad.benchmark import Entry as E, AggregatedMetric as AM, EvalReport as ER  # noqa: F401


def test_old_modules_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("operad.datasets")
    with pytest.raises(ModuleNotFoundError):
        __import__("operad.eval")
