"""Tests for `operad.benchmark.suite`."""

from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration
from operad.benchmark import (
    BenchmarkContext,
    BenchmarkMethod,
    BenchmarkReport,
    BenchmarkRunConfig,
    BenchmarkSuite,
    BenchmarkTask,
    Dataset,
    Entry,
)
from operad.core.output import OperadOutput
from operad.metrics import ExactMatch


pytestmark = pytest.mark.asyncio


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    text: str = ""


class EchoLeaf(Agent[Q, R]):
    input = Q
    output = R
    role = "echo"
    task = "echo"

    async def forward(self, x: Q) -> R:
        return R(text=x.text)


class TokenLeaf(EchoLeaf):
    def _build_envelope(self, *args: Any, **kwargs: Any) -> OperadOutput[R]:
        out = super()._build_envelope(*args, **kwargs)
        return out.model_copy(update={"prompt_tokens": 7, "completion_tokens": 3})


def _dataset(n: int = 6) -> Dataset[Q, R]:
    return Dataset(
        [
            Entry(input=Q(text=str(i)), expected_output=R(text=str(i)))
            for i in range(n)
        ],
        name="numbers",
        version="v1",
    )


def _task(cfg: Configuration) -> BenchmarkTask:
    def make_agent(offline: bool) -> Agent[Q, R]:
        assert offline is True
        return EchoLeaf(config=cfg)

    return BenchmarkTask(
        key="echo",
        name="echo",
        dataset=_dataset(),
        metrics=[ExactMatch()],
        make_seed_agent=make_agent,
        make_hand_edit_agent=make_agent,
        make_sweep_grid=lambda: {"task": ["echo", "copy"]},
    )


def _score_method(name: str, score: float, *, offline: bool = True) -> BenchmarkMethod:
    async def runner(ctx: BenchmarkContext) -> float:
        del ctx
        return score

    return BenchmarkMethod(name=name, supports_offline=offline, runner=runner)


async def test_suite_filters_tasks_methods_and_summarizes(cfg: Configuration) -> None:
    suite = BenchmarkSuite(
        [_task(cfg)],
        methods=[_score_method("a", 1.0), _score_method("b", 0.5)],
    )

    report = await suite.run(
        BenchmarkRunConfig(
            tasks=["echo"],
            methods=["a"],
            seeds=[0, 1],
            offline=True,
            metadata={"name": "suite-test"},
        )
    )

    assert len(report.cells) == 2
    assert {cell.method for cell in report.cells} == {"a"}
    assert report.summary[0].task == "echo"
    assert report.summary[0].method == "a"
    assert report.summary[0].mean == pytest.approx(1.0)
    assert report.summary[0].n == 2
    assert report.metadata == {"name": "suite-test"}
    assert BenchmarkReport.model_validate_json(report.model_dump_json()) == report
    assert not any(math.isnan(cell.score) for cell in report.cells)


async def test_suite_run_is_deterministic_for_same_seed(cfg: Configuration) -> None:
    seen: list[list[str]] = []

    async def runner(ctx: BenchmarkContext) -> float:
        test_inputs = [entry.input.text for entry in ctx.test]
        seen.append(test_inputs)
        return float(sum(int(x) for x in test_inputs))

    suite = BenchmarkSuite(
        [_task(cfg)],
        methods=[BenchmarkMethod("sum_test_inputs", True, runner)],
    )
    config = BenchmarkRunConfig(seeds=[2], offline=True)

    first = await suite.run(config)
    second = await suite.run(config)

    assert first.cells[0].score == second.cells[0].score
    assert seen[0] == seen[1]


async def test_suite_offline_default_skips_live_only_methods(cfg: Configuration) -> None:
    suite = BenchmarkSuite(
        [_task(cfg)],
        methods=[
            _score_method("offline", 1.0),
            _score_method("live", 0.0, offline=False),
        ],
    )

    report = await suite.run(BenchmarkRunConfig(seeds=[0], offline=True))

    assert [cell.method for cell in report.cells] == ["offline"]


async def test_suite_rejects_live_only_method_in_offline_mode(
    cfg: Configuration,
) -> None:
    suite = BenchmarkSuite(
        [_task(cfg)],
        methods=[_score_method("live", 1.0, offline=False)],
    )

    with pytest.raises(ValueError, match="offline mode cannot run"):
        await suite.run(
            BenchmarkRunConfig(methods=["live"], seeds=[0], offline=True)
        )


async def test_suite_counts_tokens_from_observed_end_envelopes(
    cfg: Configuration,
) -> None:
    async def runner(ctx: BenchmarkContext) -> float:
        agent = TokenLeaf(config=cfg)
        await agent.abuild()
        await agent(Q(text="hello"))
        return 1.0

    suite = BenchmarkSuite(
        [_task(cfg)],
        methods=[BenchmarkMethod("tokenized", True, runner)],
    )
    report = await suite.run(
        BenchmarkRunConfig(methods=["tokenized"], seeds=[0], offline=True)
    )

    assert report.cells[0].tokens.prompt == 7
    assert report.cells[0].tokens.completion == 3
