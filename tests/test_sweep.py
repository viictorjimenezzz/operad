"""Tests for `operad.Sweep`: Cartesian parameter grid over a seed Agent."""

from __future__ import annotations

import pytest

from operad import Agent, Sweep, SweepReport

from .conftest import A, B, FakeLeaf


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


async def test_sweep_2x3_produces_six_distinct_cells(cfg) -> None:
    seed = _EchoTask(config=cfg, task="x")
    await seed.abuild()

    params = {
        "task": ["a", "bb"],
        "role": ["r1", "r2", "r3"],
    }
    sweep = Sweep(seed, params)
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

    report = await Sweep(seed, {}).run(A(text="go"))

    assert len(report.cells) == 1
    assert report.cells[0].parameters == {}
    assert report.cells[0].output.value == 7


async def test_sweep_empty_axis_yields_empty_report(cfg) -> None:
    seed = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    await seed.abuild()

    report = await Sweep(seed, {"task": []}).run(A(text="go"))

    assert report.cells == []


async def test_sweep_rejects_grids_over_cap(cfg) -> None:
    seed = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(ValueError, match="exceeding max_combinations"):
        Sweep(seed, {"task": ["a", "b", "c"]}, max_combinations=2)


async def test_sweep_rejects_bad_concurrency(cfg) -> None:
    seed = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(ValueError, match="concurrency must be >= 1"):
        Sweep(seed, {}, concurrency=0)


async def test_sweep_does_not_mutate_seed(cfg) -> None:
    seed = _EchoTask(config=cfg, task="original")
    await seed.abuild()
    before = seed.state()

    await Sweep(
        seed, {"task": ["alt-a", "alt-b"], "role": ["x", "y"]}
    ).run(A(text="go"))

    assert seed.state() == before
    assert seed.task == "original"


async def test_sweep_report_round_trips_via_json(cfg) -> None:
    seed = _EchoTask(config=cfg, task="seed")
    await seed.abuild()

    report = await Sweep(seed, {"task": ["a", "bbb"]}).run(A(text="go"))
    raw = report.model_dump_json()
    restored = SweepReport[A, B].model_validate_json(raw)

    assert len(restored.cells) == 2
    assert {c.parameters["task"] for c in restored.cells} == {"a", "bbb"}
