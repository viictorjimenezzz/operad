"""Evolutionary: mutate-score-select over a population of Agent clones.

A population of cloned seeds is mutated, built, and evaluated against a
held-out dataset using a single `Metric`. The top half survives each
generation; the surviving agents are cloned and mutated again to fill
the population back up. Returns the best agent at the end.

Mutations always run on a fresh clone and are built before the agent
joins the population — if `abuild()` fails, the mutation is undone and
the slot is retried (up to `max_mutation_retries`) before falling back
to an unmutated clone. The seed and surviving agents are therefore
never left in a half-mutated state.

Runs entirely offline when seed/metric do (FakeLeaf seeds work). Real
LLM backends are bounded by the slot registry, not by hand-rolled
semaphores here.
"""

from __future__ import annotations

import asyncio
import copy
import random
import warnings
from typing import Generic

from ..benchmark import evaluate
from ..core.agent import Agent, In, Out
from ..metrics.base import Metric
from ..utils.errors import BuildError
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
        max_mutation_retries: int = 3,
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
        if max_mutation_retries < 1:
            raise ValueError(
                f"max_mutation_retries must be >= 1, got {max_mutation_retries}"
            )
        self.seed = seed
        self.mutations = mutations
        self.metric = metric
        self.dataset = dataset
        self.population_size = population_size
        self.generations = generations
        self.max_mutation_retries = max_mutation_retries
        self._rng = rng or random.Random()

    def _mutate(self, agent: Agent[In, Out]) -> Agent[In, Out]:
        """Deprecated: applies a mutation in place with no rollback.

        Retained for callers that relied on the old helper. Prefer
        `_attempt_mutate_and_build`, which clones, builds, and undoes
        the mutation on build failure.
        """
        op = self._rng.choice(self.mutations)
        op.apply(agent)
        return agent

    async def _attempt_mutate_and_build(
        self, parent: Agent[In, Out]
    ) -> Agent[In, Out] | None:
        """Clone `parent`, apply a random mutation, build the result.

        Returns the built, mutated clone on success. On `BuildError`
        undoes the mutation on the clone and returns `None`; the parent
        is never touched.
        """
        candidate = parent.clone()
        op = copy.deepcopy(self._rng.choice(self.mutations))
        op.apply(candidate)
        try:
            await candidate.abuild()
        except BuildError:
            op.undo(candidate)
            return None
        return candidate

    async def _fresh_individual(
        self, parent: Agent[In, Out]
    ) -> Agent[In, Out]:
        """Produce a built individual from `parent` for the population.

        Tries `_attempt_mutate_and_build` up to `max_mutation_retries`.
        On exhaustion, falls back to an unmutated built clone and warns.
        """
        for _ in range(self.max_mutation_retries):
            candidate = await self._attempt_mutate_and_build(parent)
            if candidate is not None:
                return candidate
        warnings.warn(
            "Evolutionary: all mutation attempts failed to build after "
            f"{self.max_mutation_retries} retries; using unmutated clone",
            RuntimeWarning,
            stacklevel=2,
        )
        fallback = parent.clone()
        await fallback.abuild()
        return fallback

    async def run(self) -> Agent[In, Out]:
        population: list[Agent[In, Out]] = list(
            await asyncio.gather(
                *(
                    self._fresh_individual(self.seed)
                    for _ in range(self.population_size)
                )
            )
        )
        for _ in range(self.generations):
            reports = await asyncio.gather(
                *(
                    evaluate(a, self.dataset, [self.metric])
                    for a in population
                )
            )
            scored = sorted(
                zip(reports, population),
                key=lambda pr: -pr[0].summary[self.metric.name],
            )
            half = max(1, self.population_size // 2)
            survivors = [a for _, a in scored[:half]]
            refill_parents = [
                survivors[i % len(survivors)]
                for i in range(self.population_size - len(survivors))
            ]
            refills = list(
                await asyncio.gather(
                    *(self._fresh_individual(p) for p in refill_parents)
                )
            )
            population = survivors + refills

        final_reports = await asyncio.gather(
            *(evaluate(a, self.dataset, [self.metric]) for a in population)
        )
        best_idx = max(
            range(len(population)),
            key=lambda i: final_reports[i].summary[self.metric.name],
        )
        return population[best_idx]
