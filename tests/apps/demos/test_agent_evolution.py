"""Offline tests for the agent_evolution demo.

Runs 2 generations with a fake deterministic leaf (no network). Asserts:
- generation events carry the required payload keys
- best fitness is non-decreasing across generations
- diversity is tracked (unique hash_content count <= population_size)
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "apps" / "demos" / "agent_evolution"))

from operad import Agent
from operad.metrics.metric import MetricBase
from operad.optim.optimizers.evo import EvoGradient
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import registry as obs_registry
from operad.utils.ops import AppendRule

from population import diversity  # noqa: E402 (demo helper)

pytestmark = pytest.mark.asyncio

POPULATION_SIZE = 4
GENERATIONS = 2


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

    def __init__(self, target: int = 3) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


class _EventCollector:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event: object) -> None:
        if isinstance(event, AlgorithmEvent) and event.kind == "generation":
            self.events.append(event)


async def test_generation_events_have_required_keys(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    collector = _EventCollector()
    obs_registry.register(collector)
    try:
        optimizer = EvoGradient(
            list(seed.parameters()),
            mutations=[AppendRule(path="", rule="helpful")],
            metric=_RuleCountMetric(target=3),
            dataset=[(Q(text=str(i)), R(value=3)) for i in range(3)],
            population_size=POPULATION_SIZE,
            rng=random.Random(0),
        )
        for _ in range(GENERATIONS):
            await optimizer.step()
    finally:
        obs_registry.unregister(collector)

    assert len(collector.events) == GENERATIONS
    for event in collector.events:
        p = event.payload
        assert "gen_index" in p
        assert "population_scores" in p
        assert "survivor_indices" in p
        assert "mutations" in p
        assert "individuals" in p
        assert "selected_lineage_id" in p
        assert "op_attempt_counts" in p
        assert "op_success_counts" in p
        assert len(p["population_scores"]) == POPULATION_SIZE
        assert len(p["individuals"]) == POPULATION_SIZE
        assert all("lineage_id" in row for row in p["individuals"])
    assert any(
        row["parent_lineage_id"] is not None
        for row in collector.events[1].payload["individuals"]
    )


async def test_fitness_improves_across_generations(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="helpful")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(text=str(i)), R(value=3)) for i in range(3)],
        population_size=POPULATION_SIZE,
        rng=random.Random(0),
    )

    best_scores: list[float] = []
    for _ in range(GENERATIONS):
        await optimizer.step()
        scores = optimizer._last_scores or []
        best_scores.append(max(scores) if scores else 0.0)

    assert best_scores[1] >= best_scores[0], (
        f"fitness did not improve: gen0={best_scores[0]:.3f}, gen1={best_scores[1]:.3f}"
    )


async def test_diversity_tracked_and_bounded(cfg) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="helpful")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(text=str(i)), R(value=3)) for i in range(3)],
        population_size=POPULATION_SIZE,
        rng=random.Random(0),
    )

    diversity_per_gen: list[int] = []
    for _ in range(GENERATIONS):
        await optimizer.step()
        pop = optimizer._population or []
        diversity_per_gen.append(diversity(pop))

    for d in diversity_per_gen:
        assert 1 <= d <= POPULATION_SIZE

    # diversity is non-increasing as the population converges
    assert diversity_per_gen[1] <= diversity_per_gen[0]
