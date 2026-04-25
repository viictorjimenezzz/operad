"""`EvoGradient` — population-based optimizer for an agent tree.

Each `step()` runs one generation: clone + mutate + build the current
population, evaluate every individual on a held-out dataset using a
single `Metric`, keep the top half, refill the empty slots by mutating
survivors, then copy the best agent's declared state back onto the
optimizer's root. The population is cached across `step()` calls so
multi-generation runs accumulate progress.

Unlike `TextualGradientDescent`, `EvoGradient` ignores
`Parameter.grad` entirely — it drives selection via discrete `Op`
mutations plus metric feedback, not textual gradients. Opting into
`EvoGradient` means opting out of the textual-gradient flow for its
lifetime.
"""

from __future__ import annotations

import asyncio
import copy
import random
import statistics
import warnings
from typing import Any, Iterable

from operad.benchmark.evaluate import evaluate
from operad.core.agent import Agent
from operad.metrics.base import Metric
from operad.optim.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter
from operad.runtime.observers.base import (
    _enter_algorithm_run,
    emit_algorithm_event,
)
from operad.utils.errors import BuildError
from operad.utils.ops import Op


_IDENTITY_OP = "identity"


class EvoGradient(Optimizer):
    """Evolutionary optimizer that mutates the whole agent tree.

    The brief for this class lives at
    `.conductor/optim/4-1-optimizer-fleet.md`. Each `step()` runs one
    generation; callers loop `step()` to run a full run. After every
    step the best individual's declared state is written back to the
    root via `Agent.load_state`, so the root agent the caller passed in
    tracks the best-so-far.
    """

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        lr: float = 1.0,
        *,
        mutations: list[Op],
        metric: Metric,
        dataset: list[tuple[Any, Any]],
        population_size: int = 8,
        rng: random.Random | None = None,
        max_mutation_retries: int = 3,
        max_mutation_entries: int = 200,
    ) -> None:
        if population_size < 2:
            raise ValueError(
                f"population_size must be >= 2, got {population_size}"
            )
        if not mutations:
            raise ValueError("mutations must not be empty")
        if not dataset:
            raise ValueError("dataset must not be empty")
        if max_mutation_retries < 1:
            raise ValueError(
                f"max_mutation_retries must be >= 1, got {max_mutation_retries}"
            )
        super().__init__(params, defaults={"lr": lr, "momentum": 0.0})
        self._mutations = list(mutations)
        self._metric = metric
        self._dataset = list(dataset)
        self._population_size = int(population_size)
        self._max_mutation_retries = int(max_mutation_retries)
        self._max_mutation_entries = int(max_mutation_entries)
        self._rng = rng or random.Random()
        self._population: list[Agent[Any, Any]] | None = None
        self._generation = 0
        self._root = self._discover_root()
        # Tracks (individual→(op_name, path)) via id() of each agent in
        # the current population so attribution survives across
        # generations (survivors keep their creation op). Path is the
        # dotted path the op targeted in the tree, used by observers
        # (e.g. the dashboard graph panel) to attribute changes to a
        # specific sub-agent.
        self._origin_ops: dict[int, tuple[str, str]] = {}
        # Scores evaluated during the most recent step(), used to compute
        # the "improved vs previous generation median" flag on the next
        # emission. Seeded from a one-off root eval on the first step.
        self._last_scores: list[float] | None = None

    def _discover_root(self) -> Agent[Any, Any]:
        for group in self.param_groups:
            for p in group.params:
                return p._agent()
        raise ValueError("EvoGradient got no parameters with attached agents")

    async def _attempt_mutate_and_build(
        self, parent: Agent[Any, Any]
    ) -> tuple[Agent[Any, Any], str, str] | None:
        candidate = parent.clone()
        op = copy.deepcopy(self._rng.choice(self._mutations))
        op.apply(candidate)
        try:
            await candidate.abuild()
        except BuildError:
            op.undo(candidate)
            return None
        return candidate, op.name, getattr(op, "path", "")

    async def _fresh_individual(
        self, parent: Agent[Any, Any]
    ) -> Agent[Any, Any]:
        for _ in range(self._max_mutation_retries):
            outcome = await self._attempt_mutate_and_build(parent)
            if outcome is not None:
                candidate, op_name, op_path = outcome
                self._origin_ops[id(candidate)] = (op_name, op_path)
                return candidate
        warnings.warn(
            "EvoGradient: all mutation attempts failed to build after "
            f"{self._max_mutation_retries} retries; using unmutated clone",
            RuntimeWarning,
            stacklevel=2,
        )
        fallback = parent.clone()
        await fallback.abuild()
        self._origin_ops[id(fallback)] = (_IDENTITY_OP, "")
        return fallback

    async def step(self) -> None:
        if self._population is None:
            await self._emit_algo_start()
            # Seed-score baseline drives the first-generation `improved`
            # comparisons: every initial individual is judged against
            # how the unmutated root scored on the same dataset.
            seed_report = await evaluate(
                self._root, self._dataset, [self._metric]
            )
            self._last_scores = [
                float(seed_report.summary[self._metric.name])
            ]
            self._population = list(
                await asyncio.gather(
                    *(
                        self._fresh_individual(self._root)
                        for _ in range(self._population_size)
                    )
                )
            )

        reports = await asyncio.gather(
            *(
                evaluate(a, self._dataset, [self._metric])
                for a in self._population
            )
        )
        scores = [
            float(r.summary[self._metric.name]) for r in reports
        ]
        ranked = sorted(
            enumerate(reports),
            key=lambda ir: -ir[1].summary[self._metric.name],
        )
        half = max(1, self._population_size // 2)
        survivor_indices = [i for i, _ in ranked[:half]]
        survivors = [self._population[i] for i in survivor_indices]

        await self._emit_generation_event(
            population=self._population,
            scores=scores,
            survivor_indices=survivor_indices,
        )

        refill_parents = [
            survivors[i % len(survivors)]
            for i in range(self._population_size - len(survivors))
        ]
        refills = list(
            await asyncio.gather(
                *(self._fresh_individual(p) for p in refill_parents)
            )
        )
        new_population = survivors + refills
        # Drop provenance for individuals that did not survive into the
        # next generation so the dict does not leak across many steps.
        kept_ids = {id(a) for a in new_population}
        self._origin_ops = {
            k: v for k, v in self._origin_ops.items() if k in kept_ids
        }
        self._population = new_population

        best = survivors[0]
        await self._write_back(best)
        self._last_scores = scores
        self._generation += 1

    async def _emit_algo_start(self) -> None:
        """Announce the run with the root agent's identity and Mermaid graph.

        The dashboard uses `root_path` to anchor mutation paths to graph
        node IDs (mutation paths are root-relative, but Mermaid IDs are
        rooted at the agent class name) and uses `graph_mermaid` to
        render the topology on the algorithm run's graph panel — agent
        evaluations during a run carry separate run_ids, so without
        this the algorithm run has no graph to render.
        """
        from operad.core.graph import to_mermaid

        graph_mermaid: str | None = None
        graph = getattr(self._root, "_graph", None)
        if graph is not None:
            try:
                graph_mermaid = to_mermaid(graph)
            except Exception:
                graph_mermaid = None
        payload: dict[str, Any] = {
            "root_path": type(self._root).__name__,
            "population_size": self._population_size,
        }
        if graph_mermaid is not None:
            payload["graph_mermaid"] = graph_mermaid
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=type(self).__name__,
                payload=payload,
            )

    async def _emit_generation_event(
        self,
        *,
        population: list[Agent[Any, Any]],
        scores: list[float],
        survivor_indices: list[int],
    ) -> None:
        baseline = self._last_scores or []
        median = statistics.median(baseline) if baseline else float("-inf")
        origins = [
            self._origin_ops.get(id(a), (_IDENTITY_OP, "")) for a in population
        ]
        ops = [o[0] for o in origins]
        paths = [o[1] for o in origins]
        improved = [s > median for s in scores]
        mutations: list[dict[str, Any]] = [
            {
                "individual_id": i,
                "op": ops[i],
                "path": paths[i],
                "improved": bool(improved[i]),
            }
            for i in range(len(population))
        ]
        attempt_counts: dict[str, int] = {}
        success_counts: dict[str, int] = {}
        for i, op_name in enumerate(ops):
            attempt_counts[op_name] = attempt_counts.get(op_name, 0) + 1
            if improved[i]:
                success_counts[op_name] = success_counts.get(op_name, 0) + 1
        payload: dict[str, Any] = {
            "gen_index": self._generation,
            "population_scores": scores,
            "survivor_indices": list(survivor_indices),
            "mutations": mutations[: self._max_mutation_entries],
            "op_attempt_counts": attempt_counts,
            "op_success_counts": success_counts,
        }
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "generation",
                algorithm_path=type(self).__name__,
                payload=payload,
            )

    async def _write_back(self, best: Agent[Any, Any]) -> None:
        """Copy `best`'s declared state onto the root and refresh tracked params."""
        self._root.load_state(best.state())
        await self._root.abuild()
        for _, p in self.named_parameters():
            p.read()

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        raise NotImplementedError(
            "EvoGradient overrides step() and does not use per-parameter updates"
        )


__all__ = ["EvoGradient"]
