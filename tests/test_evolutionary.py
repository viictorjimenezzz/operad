"""Tests for `operad.Evolutionary`."""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import (
    Agent,
    AppendRule,
    Evolutionary,
)


pytestmark = pytest.mark.asyncio


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class _RuleCountLeaf(Agent[Q, R]):
    """Leaf whose output is driven by how many rules it currently has.

    This lets us write a deterministic metric whose score improves as
    mutations append rules — a toy but honest proxy for "evolution can
    make the seed better".
    """

    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


from operad import MetricBase


class _RuleCountMetric(MetricBase):
    """Scores predicted.value toward a target rule count."""

    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        # Saturate at target; penalise distance.
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


async def test_evolutionary_evolves_seed(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []  # start with zero rules
    await seed.abuild()

    dataset = [
        (Q(text="a"), R(value=3)),
        (Q(text="b"), R(value=3)),
        (Q(text="c"), R(value=3)),
    ]
    mutations = [AppendRule(path="", rule="helpful")]
    metric = _RuleCountMetric(target=3)

    evo = Evolutionary(
        seed=seed,
        mutations=mutations,
        metric=metric,
        dataset=dataset,
        population_size=4,
        generations=3,
        rng=random.Random(42),
    )
    best = await evo.run()
    # Seed score at rule_count=0 is 1 - 3/3 = 0.0.
    # With AppendRule every generation, survivors climb toward target=3.
    assert len(best.rules) >= 1
    assert isinstance(best, _RuleCountLeaf)
    assert best is not seed  # clone, not the original


async def test_evolutionary_rejects_empty_mutations(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    with pytest.raises(ValueError, match="mutations"):
        Evolutionary(
            seed=seed,
            mutations=[],
            metric=_RuleCountMetric(1),
            dataset=[(Q(), R())],
        )


async def test_evolutionary_rejects_empty_dataset(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    with pytest.raises(ValueError, match="dataset"):
        Evolutionary(
            seed=seed,
            mutations=[AppendRule(path="", rule="x")],
            metric=_RuleCountMetric(1),
            dataset=[],
        )


async def test_evolutionary_rejects_small_population(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    with pytest.raises(ValueError, match="population_size"):
        Evolutionary(
            seed=seed,
            mutations=[AppendRule(path="", rule="x")],
            metric=_RuleCountMetric(1),
            dataset=[(Q(), R())],
            population_size=1,
        )
