"""Tests for `operad.benchmark.sensitivity`."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration, Dataset, evaluate
from operad.benchmark import (
    SensitivityCell,
    SensitivityReport,
    sensitivity,
)
from operad.metrics.metric import MetricBase

from .conftest import A, FakeLeaf


pytestmark = pytest.mark.asyncio


class Scored(BaseModel):
    value: float = 0.0


class ValueMetric(MetricBase):
    """Return the predicted value directly (higher is better)."""

    name = "value"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return float(predicted.value)  # type: ignore[attr-defined]


class ConfigSensitiveLeaf(Agent[A, Scored]):
    """FakeLeaf-shaped leaf that outputs a function of its current config."""

    input = A
    output = Scored

    def __init__(
        self,
        *,
        config: Configuration,
        w_temp: float = 0.0,
        w_top_p: float = 0.0,
    ) -> None:
        super().__init__(config=config, input=A, output=Scored)
        self.w_temp = w_temp
        self.w_top_p = w_top_p

    async def forward(self, x: A) -> Scored:  # type: ignore[override]
        t = self.config.sampling.temperature
        p = self.config.sampling.top_p or 0.0
        return Scored.model_construct(value=self.w_temp * t + self.w_top_p * p)


async def test_baseline_matches_evaluate(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=Scored, canned={"value": 0.42}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")
    metric = ValueMetric()

    report = await sensitivity(
        agent,
        ds,
        metric,
        perturbations={"config.sampling.temperature": [0.1]},
    )

    direct = await evaluate(agent, ds, [metric])
    assert report.baseline == pytest.approx(direct.summary[metric.name])
    assert report.baseline == pytest.approx(0.42)


async def test_explicit_perturbation_cells_present(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=Scored, canned={"value": 1.0}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    report = await sensitivity(
        agent,
        ds,
        ValueMetric(),
        perturbations={"config.sampling.temperature": [0.1, 0.9]},
    )

    assert isinstance(report, SensitivityReport)
    temp_cells = [c for c in report.cells if c.parameter == "config.sampling.temperature"]
    assert len(temp_cells) == 2
    assert {c.value for c in temp_cells} == {0.1, 0.9}
    for cell in temp_cells:
        assert isinstance(cell, SensitivityCell)


async def test_ranking_orders_by_abs_delta(cfg) -> None:
    # top_p perturbations swing the output far; temperature perturbations
    # barely move it. Baseline uses the agent's current config values.
    config = cfg.model_copy(
        update={"sampling": cfg.sampling.model_copy(update={"top_p": 0.5})}
    )
    agent = ConfigSensitiveLeaf(config=config, w_temp=0.01, w_top_p=1.0)
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    report = await sensitivity(
        agent,
        ds,
        ValueMetric(),
        perturbations={
            "config.sampling.temperature": [0.51, 0.52],
            "config.sampling.top_p": [0.2, 0.9],
        },
    )

    assert report.ranking[0][0] == "config.sampling.top_p"
    assert report.ranking[1][0] == "config.sampling.temperature"
    top_delta = next(d for p, d in report.ranking if p == "config.sampling.top_p")
    temp_delta = next(d for p, d in report.ranking if p == "config.sampling.temperature")
    assert top_delta > temp_delta


async def test_ranking_tie_break_on_path_string(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=Scored, canned={"value": 0.5}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    # Canned output ignores config, so every perturbation yields the same
    # score (delta=0). Tie-break must sort paths alphabetically.
    report = await sensitivity(
        agent,
        ds,
        ValueMetric(),
        perturbations={
            "config.sampling.top_p": [0.1, 0.2],
            "config.sampling.temperature": [0.1, 0.2],
        },
    )

    paths = [p for p, _ in report.ranking]
    assert paths == ["config.sampling.temperature", "config.sampling.top_p"]


async def test_default_perturbations_probes_sampling_axes(cfg) -> None:
    config = cfg.model_copy(
        update={
            "sampling": cfg.sampling.model_copy(
                update={"temperature": 0.5, "top_p": 0.5, "top_k": 40}
            )
        }
    )
    agent = FakeLeaf(
        config=config, input=A, output=Scored, canned={"value": 0.0}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    report = await sensitivity(agent, ds, ValueMetric())

    probed = {cell.parameter for cell in report.cells}
    allowed = {
        "config.sampling.temperature",
        "config.sampling.top_p",
        "config.sampling.top_k",
        "config.sampling.max_tokens",
    }
    assert probed.issubset(allowed)
    assert "config.sampling.temperature" in probed
    # The ``cfg`` fixture sets top_p / top_k to None; after our update top_p
    # and top_k are non-None, so they should also be probed.
    assert "config.sampling.top_p" in probed
    assert "config.sampling.top_k" in probed
    # max_tokens=16 from cfg fixture → non-None → probed.
    assert "config.sampling.max_tokens" in probed


class _ClassCounter:
    active = 0
    peak = 0


class _ClassCountingLeaf(Agent[A, Scored]):
    """Uses class-level counters so clones share the same state."""

    input = A
    output = Scored

    async def forward(self, x: A) -> Scored:  # type: ignore[override]
        import asyncio

        _ClassCounter.active += 1
        _ClassCounter.peak = max(_ClassCounter.peak, _ClassCounter.active)
        await asyncio.sleep(0.01)
        _ClassCounter.active -= 1
        return Scored.model_construct(value=0.0)


async def test_concurrency_one_serialises_evaluations(cfg) -> None:
    _ClassCounter.active = 0
    _ClassCounter.peak = 0
    agent = _ClassCountingLeaf(config=cfg, input=A, output=Scored)
    await agent.abuild()
    ds = Dataset(
        [(A(text=f"q{i}"), Scored(value=0.0)) for i in range(3)], name="t"
    )

    await sensitivity(
        agent,
        ds,
        ValueMetric(),
        perturbations={"config.sampling.temperature": [0.1, 0.5, 0.9]},
        concurrency=1,
    )

    # Outer fan-out = 1 and inner evaluate concurrency is pinned to 1 →
    # at most one forward call runs at any instant.
    assert _ClassCounter.peak == 1


async def test_agent_unchanged_after_sensitivity(cfg) -> None:
    config = cfg.model_copy(
        update={"sampling": cfg.sampling.model_copy(update={"temperature": 0.3})}
    )
    agent = FakeLeaf(
        config=config, input=A, output=Scored, canned={"value": 0.7}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    await sensitivity(
        agent,
        ds,
        ValueMetric(),
        perturbations={"config.sampling.temperature": [0.1, 0.9]},
    )

    assert agent.config.sampling.temperature == 0.3


async def test_invalid_path_raises_value_error(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=Scored, canned={"value": 0.0}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    with pytest.raises(ValueError, match="invalid perturbation path"):
        await sensitivity(
            agent,
            ds,
            ValueMetric(),
            perturbations={"config.nonexistent_field_xyz.inner": [1.0]},
        )


async def test_max_combinations_cap(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=Scored, canned={"value": 0.0}
    )
    await agent.abuild()
    ds = Dataset([(A(text="q1"), Scored(value=0.0))], name="t")

    with pytest.raises(ValueError, match="exceeding max_combinations"):
        await sensitivity(
            agent,
            ds,
            ValueMetric(),
            perturbations={"config.sampling.temperature": [0.1, 0.2, 0.3]},
            max_combinations=2,
        )
