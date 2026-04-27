"""Tests for `Agent.auto_tune` and `default_mutations`."""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.benchmark.dataset import Dataset
from operad.metrics.metric import MetricBase
from operad.utils.ops import (
    AppendRule,
    EditTask,
    SetTemperature,
    TweakRole,
    default_mutations,
)


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class _RuleCountLeaf(Agent[Q, R]):
    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


class _RuleCountMetric(MetricBase):
    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


def _seed(cfg) -> _RuleCountLeaf:
    s = _RuleCountLeaf(config=cfg, task="count rules")
    s.role = "You are a counter."
    s.rules = []
    return s


async def test_auto_tune_improves_metric(cfg) -> None:
    seed = _seed(cfg)
    await seed.abuild()

    dataset = [(Q(text="a"), R(value=3))] * 3
    metric = _RuleCountMetric(target=3)

    # Use only rule-appending mutations so improvement is deterministic.
    best = await seed.auto_tune(
        dataset,
        metric,
        mutations=[AppendRule(path="", rule="be thorough")],
        population_size=4,
        generations=3,
        rng=random.Random(42),
    )
    assert isinstance(best, _RuleCountLeaf)
    assert len(best.rules) >= 1
    assert best is not seed


async def test_auto_tune_does_not_mutate_seed(cfg) -> None:
    seed = _seed(cfg)
    await seed.abuild()
    before = seed.state()

    dataset = [(Q(text="a"), R(value=3))]
    metric = _RuleCountMetric(target=3)

    await seed.auto_tune(
        dataset,
        metric,
        mutations=[AppendRule(path="", rule="be thorough")],
        population_size=2,
        generations=2,
        rng=random.Random(0),
    )
    assert seed.state() == before


async def test_auto_tune_accepts_dataset_object(cfg) -> None:
    seed = _seed(cfg)
    await seed.abuild()

    ds = Dataset(
        [(Q(text="a"), R(value=3)), (Q(text="b"), R(value=3))],
        in_cls=Q,
        out_cls=R,
    )
    metric = _RuleCountMetric(target=3)
    best = await seed.auto_tune(
        ds,
        metric,
        mutations=[AppendRule(path="", rule="x")],
        population_size=2,
        generations=1,
        rng=random.Random(1),
    )
    assert isinstance(best, _RuleCountLeaf)


async def test_auto_tune_uses_default_mutations(cfg) -> None:
    """With `mutations=None`, the default set wires in and the run completes."""
    seed = _seed(cfg)
    await seed.abuild()

    dataset = [(Q(text="a"), R(value=0))]
    metric = _RuleCountMetric(target=3)
    best = await seed.auto_tune(
        dataset,
        metric,
        population_size=2,
        generations=1,
        rng=random.Random(0),
    )
    assert isinstance(best, _RuleCountLeaf)


def test_default_mutations_covers_categories(cfg) -> None:
    agent = _seed(cfg)
    ops = default_mutations(agent)
    kinds = {type(o) for o in ops}
    assert AppendRule in kinds
    assert TweakRole in kinds
    assert EditTask in kinds
    assert SetTemperature in kinds
    assert len(ops) <= 12


def test_default_mutations_skips_temperature_without_config() -> None:
    agent = _RuleCountLeaf(
        config=None,
        task="count",
        input=Q,
        output=R,
    )
    ops = default_mutations(agent)
    assert not any(isinstance(o, SetTemperature) for o in ops)


def test_default_mutations_skips_edit_task_when_empty(cfg) -> None:
    agent = _RuleCountLeaf(config=cfg, task="")
    ops = default_mutations(agent)
    assert not any(isinstance(o, EditTask) for o in ops)
