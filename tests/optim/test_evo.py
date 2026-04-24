"""Tests for `operad.optim.EvoGradient`."""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import registry as obs_registry
from operad.utils.errors import BuildError
from operad.utils.ops import AppendRule, TweakRole


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


class _AlgoCollector:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event: object) -> None:
        if isinstance(event, AlgorithmEvent):
            self.events.append(event)


@pytest.fixture
def _algo_collector():
    col = _AlgoCollector()
    obs_registry.register(col)
    try:
        yield col
    finally:
        obs_registry.unregister(col)


async def test_generation_event_carries_mutation_attribution(
    cfg, _algo_collector: _AlgoCollector
) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    dataset = [(Q(text="x"), R(value=3))]
    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[
            AppendRule(path="", rule="helpful"),
            TweakRole(path="", role="friendly"),
        ],
        metric=_RuleCountMetric(target=3),
        dataset=dataset,
        population_size=4,
        rng=random.Random(0),
    )

    await optimizer.step()

    gen_events = [e for e in _algo_collector.events if e.kind == "generation"]
    assert len(gen_events) == 1
    payload = gen_events[0].payload
    assert payload["gen_index"] == 0
    assert len(payload["population_scores"]) == 4
    assert len(payload["survivor_indices"]) == 2  # top half of size-4 pop
    muts = payload["mutations"]
    assert len(muts) == 4
    valid_ops = {"append_rule", "tweak_role", "identity"}
    assert all(m["op"] in valid_ops for m in muts)
    assert sum(payload["op_attempt_counts"].values()) == 4
    for op, successes in payload["op_success_counts"].items():
        assert successes <= payload["op_attempt_counts"][op]


async def test_generation_events_across_multiple_steps(
    cfg, _algo_collector: _AlgoCollector
) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="helpful")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(), R(value=3))],
        population_size=4,
        rng=random.Random(1),
    )
    for _ in range(3):
        await optimizer.step()

    gens = [e for e in _algo_collector.events if e.kind == "generation"]
    assert [g.payload["gen_index"] for g in gens] == [0, 1, 2]
    # Every generation emits one event with a populated mutations list.
    for g in gens:
        assert len(g.payload["mutations"]) == 4


async def test_mutation_entry_soft_cap(cfg, _algo_collector: _AlgoCollector) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="helpful")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(), R(value=3))],
        population_size=4,
        rng=random.Random(2),
        max_mutation_entries=2,
    )
    await optimizer.step()

    gen = [e for e in _algo_collector.events if e.kind == "generation"][0]
    assert len(gen.payload["mutations"]) == 2
    # Aggregate counts still reflect the full population (4), not the cap.
    assert sum(gen.payload["op_attempt_counts"].values()) == 4


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
