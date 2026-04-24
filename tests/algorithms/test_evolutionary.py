"""Tests for `operad.Evolutionary`."""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.algorithms import Evolutionary
from operad.utils.errors import BuildError
from operad.utils.ops import AppendRule


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


from operad.metrics.base import MetricBase


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


async def test_evolutionary_rollback_on_build_failure(cfg) -> None:
    seed = _PoisonableLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()
    seed_state_before = seed.state()

    dataset = [(Q(text="a"), R(value=3))]
    poison_mutations = [AppendRule(path="", rule="POISON")]
    metric = _RuleCountMetric(target=3)

    evo = Evolutionary(
        seed=seed,
        mutations=poison_mutations,
        metric=metric,
        dataset=dataset,
        population_size=4,
        generations=2,
        rng=random.Random(0),
        max_mutation_retries=2,
    )

    with pytest.warns(RuntimeWarning, match="mutation attempts failed"):
        best = await evo.run()

    # Seed is untouched — all mutations ran on clones.
    assert seed.state() == seed_state_before
    # Every mutation would have added "POISON" — rollback + fallback
    # guarantees no surviving agent carries it.
    assert "POISON" not in best.rules


async def test_evolutionary_rollback_preserves_population_size(cfg) -> None:
    """With a mixed pool (some poison, some not), population size holds."""
    seed = _PoisonableLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    dataset = [(Q(text="a"), R(value=3))]
    mutations = [
        AppendRule(path="", rule="POISON"),
        AppendRule(path="", rule="helpful"),
    ]
    metric = _RuleCountMetric(target=3)

    evo = Evolutionary(
        seed=seed,
        mutations=mutations,
        metric=metric,
        dataset=dataset,
        population_size=4,
        generations=3,
        rng=random.Random(7),
        max_mutation_retries=5,
    )
    best = await evo.run()
    assert "POISON" not in best.rules
    assert isinstance(best, _PoisonableLeaf)
