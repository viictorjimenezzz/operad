"""Tests for `operad.optim.EvoGradient`."""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.utils.errors import BuildError
from operad.utils.ops import AppendRule


pytestmark = pytest.mark.asyncio


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class _RuleCountLeaf(Agent[Q, R]):
    """Leaf whose output is driven by how many rules it currently has."""

    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


class _RuleCountMetric(MetricBase):
    """Scores predicted.value toward a target rule count."""

    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


async def test_evo_gradient_evolves_root(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    dataset = [
        (Q(text="a"), R(value=3)),
        (Q(text="b"), R(value=3)),
        (Q(text="c"), R(value=3)),
    ]
    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="helpful")],
        metric=_RuleCountMetric(target=3),
        dataset=dataset,
        population_size=4,
        rng=random.Random(42),
    )
    for _ in range(3):
        await optimizer.step()

    assert len(seed.rules) >= 1
    assert isinstance(seed, _RuleCountLeaf)
    assert optimizer._population is not None
    assert len(optimizer._population) == 4
    assert optimizer._generation == 3


async def test_evo_gradient_rejects_empty_mutations(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    await seed.abuild()
    with pytest.raises(ValueError, match="mutations"):
        EvoGradient(
            list(seed.parameters()),
            mutations=[],
            metric=_RuleCountMetric(1),
            dataset=[(Q(), R())],
        )


async def test_evo_gradient_rejects_empty_dataset(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    await seed.abuild()
    with pytest.raises(ValueError, match="dataset"):
        EvoGradient(
            list(seed.parameters()),
            mutations=[AppendRule(path="", rule="x")],
            metric=_RuleCountMetric(1),
            dataset=[],
        )


async def test_evo_gradient_rejects_small_population(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    await seed.abuild()
    with pytest.raises(ValueError, match="population_size"):
        EvoGradient(
            list(seed.parameters()),
            mutations=[AppendRule(path="", rule="x")],
            metric=_RuleCountMetric(1),
            dataset=[(Q(), R())],
            population_size=1,
        )


class _PoisonableLeaf(_RuleCountLeaf):
    """`_RuleCountLeaf` whose `abuild` refuses to build when poisoned."""

    async def abuild(self):  # type: ignore[override]
        if "POISON" in self.rules:
            raise BuildError(
                "prompt_incomplete",
                "poisoned by sentinel rule",
                agent=type(self).__name__,
            )
        return await super().abuild()


async def test_evo_gradient_rollback_on_build_failure(cfg) -> None:
    seed = _PoisonableLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="POISON")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(text="a"), R(value=3))],
        population_size=4,
        rng=random.Random(0),
        max_mutation_retries=2,
    )

    with pytest.warns(RuntimeWarning, match="mutation attempts failed"):
        for _ in range(2):
            await optimizer.step()

    # Every mutation attempts to append "POISON" — rollback + fallback
    # guarantees no surviving agent (and therefore the root) carries it.
    assert "POISON" not in seed.rules


async def test_evo_gradient_rollback_preserves_population_size(cfg) -> None:
    """With a mixed pool (some poison, some not), population size holds."""
    seed = _PoisonableLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[
            AppendRule(path="", rule="POISON"),
            AppendRule(path="", rule="helpful"),
        ],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(text="a"), R(value=3))],
        population_size=4,
        rng=random.Random(7),
        max_mutation_retries=5,
    )
    for _ in range(3):
        await optimizer.step()

    assert "POISON" not in seed.rules
    assert isinstance(seed, _PoisonableLeaf)
    assert len(optimizer._population) == 4
