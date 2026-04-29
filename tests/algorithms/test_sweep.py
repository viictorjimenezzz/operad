"""Tests for `operad.Sweep`: Cartesian parameter grid over a seed Agent."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents.reasoning.schemas import Candidate, Score
from operad.algorithms import Sweep, SweepReport

from ..conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class _EchoTask(Agent[A, B]):
    """Leaf whose output encodes its current `task` string length.

    Makes it trivial to verify that per-clone re-parameterisation lands
    on the clone (not the seed) and that each cell's output comes from
    the combination it was built with.
    """

    input = A
    output = B

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=len(self.task))


class _ScoreByValue(Agent[Candidate[A, B], Score]):
    input = Candidate
    output = Score

    async def forward(self, x: Candidate[A, B]) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0)
        return Score(score=float(value) / 10.0, rationale=f"value={value}")


async def _make_sweep(seed: Agent, params: dict, **kwargs) -> Sweep:
    sweep = Sweep(params, **kwargs)
    sweep.seed = seed
    return sweep


async def test_sweep_2x3_produces_six_distinct_cells(cfg) -> None:
    seed = _EchoTask(config=cfg, task="x")
    await seed.abuild()

    params = {
        "task": ["a", "bb"],
        "role": ["r1", "r2", "r3"],
    }
    sweep = await _make_sweep(seed, params)
    report = await sweep.run(A(text="go"))

    assert isinstance(report, SweepReport)
    assert len(report.cells) == 6
    combos = {(c.parameters["task"], c.parameters["role"]) for c in report.cells}
    assert combos == {
        (t, r) for t in params["task"] for r in params["role"]
    }
    for cell in report.cells:
        assert cell.output.value == len(cell.parameters["task"])


async def test_sweep_empty_parameters_yields_single_cell(cfg) -> None:
    seed = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7})
    await seed.abuild()

    sweep = await _make_sweep(seed, {})
    report = await sweep.run(A(text="go"))

    assert len(report.cells) == 1
    assert report.cells[0].parameters == {}
    assert report.cells[0].output.value == 7


async def test_sweep_empty_axis_yields_empty_report(cfg) -> None:
    seed = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    await seed.abuild()

    sweep = await _make_sweep(seed, {"task": []})
    report = await sweep.run(A(text="go"))

    assert report.cells == []


async def test_sweep_rejects_grids_over_cap() -> None:
    with pytest.raises(ValueError, match="exceeding max_combinations"):
        Sweep({"task": ["a", "b", "c"]}, max_combinations=2)


async def test_sweep_rejects_bad_concurrency() -> None:
    with pytest.raises(ValueError, match="concurrency must be >= 1"):
        Sweep({}, concurrency=0)


async def test_sweep_does_not_mutate_seed(cfg) -> None:
    seed = _EchoTask(config=cfg, task="original")
    await seed.abuild()
    before = seed.state()

    sweep = await _make_sweep(
        seed, {"task": ["alt-a", "alt-b"], "role": ["x", "y"]}
    )
    await sweep.run(A(text="go"))

    assert seed.state() == before
    assert seed.task == "original"


async def test_sweep_report_round_trips_via_json(cfg) -> None:
    seed = _EchoTask(config=cfg, task="seed")
    await seed.abuild()

    sweep = await _make_sweep(seed, {"task": ["a", "bbb"]})
    report = await sweep.run(A(text="go"))
    raw = report.model_dump_json()
    restored = SweepReport[A, B].model_validate_json(raw)

    assert len(restored.cells) == 2
    assert {c.parameters["task"] for c in restored.cells} == {"a", "bbb"}


async def test_sweep_judge_scores_cells_and_records_child_refs(cfg) -> None:
    seed = _EchoTask(config=cfg, task="x")
    await seed.abuild()

    sweep = await _make_sweep(seed, {"task": ["a", "bbb"]})
    sweep.judge = _ScoreByValue(config=cfg)

    report = await sweep.run(A(text="go"))

    assert [cell.score for cell in report.cells] == [0.1, 0.3]
    assert [cell.judge_rationale for cell in report.cells] == ["value=1", "value=3"]
    assert all(cell.child_run_id for cell in report.cells)
    assert all(cell.judge_run_id for cell in report.cells)
