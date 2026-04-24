"""Evolutionary: mutate-score-select over a population of Agent clones.

A population of cloned seeds is mutated, built, and evaluated against a
held-out dataset using a single `Metric`. The top half survives each
generation; the surviving agents are cloned and mutated again to fill
the population back up. Returns the best agent at the end.

Runs entirely offline when seed/metric do (FakeLeaf seeds work). Real
LLM backends are bounded by the slot registry, not by hand-rolled
semaphores here.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Generic

from ..core.agent import Agent, In, Out
from ..benchmark import evaluate
from ..metrics.base import Metric
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from ..utils.ops import Op


class Evolutionary(Generic[In, Out]):
    def __init__(
        self,
        seed: Agent[In, Out],
        mutations: list[Op],
        metric: Metric,
        dataset: list[tuple[In, Out]],
        *,
        population_size: int = 8,
        generations: int = 4,
        rng: random.Random | None = None,
    ) -> None:
        if population_size < 2:
            raise ValueError(
                f"population_size must be >= 2, got {population_size}"
            )
        if generations < 1:
            raise ValueError(f"generations must be >= 1, got {generations}")
        if not mutations:
            raise ValueError("mutations must not be empty")
        if not dataset:
            raise ValueError("dataset must not be empty")
        self.seed = seed
        self.mutations = mutations
        self.metric = metric
        self.dataset = dataset
        self.population_size = population_size
        self.generations = generations
        self._rng = rng or random.Random()

    def _mutate(self, agent: Agent[In, Out]) -> Agent[In, Out]:
        op = self._rng.choice(self.mutations)
        op.apply(agent)
        return agent

    async def run(self) -> Agent[In, Out]:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={
                    "population_size": self.population_size,
                    "generations": self.generations,
                    "metric": self.metric.name,
                },
                started_at=started,
            )
            try:
                population: list[Agent[In, Out]] = [
                    self._mutate(self.seed.clone()) for _ in range(self.population_size)
                ]
                for gen_index in range(self.generations):
                    await asyncio.gather(*(a.abuild() for a in population))
                    reports = await asyncio.gather(
                        *(
                            evaluate(a, self.dataset, [self.metric])
                            for a in population
                        )
                    )
                    indexed = list(enumerate(reports))
                    indexed_sorted = sorted(
                        indexed,
                        key=lambda ir: -ir[1].summary[self.metric.name],
                    )
                    half = max(1, self.population_size // 2)
                    survivor_indices = [i for i, _ in indexed_sorted[:half]]
                    population_scores = [
                        r.summary[self.metric.name] for r in reports
                    ]
                    await emit_algorithm_event(
                        "generation",
                        algorithm_path=path,
                        payload={
                            "gen_index": gen_index,
                            "population_scores": population_scores,
                            "survivor_indices": survivor_indices,
                        },
                    )
                    survivors = [population[i] for i in survivor_indices]
                    refills = [
                        self._mutate(a.clone())
                        for a in (
                            survivors[i % len(survivors)]
                            for i in range(self.population_size - len(survivors))
                        )
                    ]
                    population = survivors + refills

                await asyncio.gather(*(a.abuild() for a in population))
                final_reports = await asyncio.gather(
                    *(evaluate(a, self.dataset, [self.metric]) for a in population)
                )
                best_idx = max(
                    range(len(population)),
                    key=lambda i: final_reports[i].summary[self.metric.name],
                )
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "best_index": best_idx,
                        "score": final_reports[best_idx].summary[self.metric.name],
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return population[best_idx]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise
