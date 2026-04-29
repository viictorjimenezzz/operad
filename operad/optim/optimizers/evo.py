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
import contextlib
import copy
from dataclasses import dataclass
import json
import random
import statistics
import uuid
import warnings
from typing import Any, AsyncIterator, Iterable

from pydantic import BaseModel

from operad.benchmark.evaluate import evaluate
from operad.core.agent import Agent
from operad.metrics.metric import Metric
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter
from operad.runtime.observers.base import (
    _enter_algorithm_metadata,
    _enter_algorithm_run,
    emit_algorithm_event,
)
from operad.utils.errors import BuildError
from operad.utils.ops import Op


_IDENTITY_OP = "identity"


@dataclass(frozen=True)
class _IndividualOrigin:
    op: str
    path: str
    lineage_id: str
    parent_lineage_id: str | None
    parameter_deltas: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Optimizer.
# ---------------------------------------------------------------------------


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
        # Tracks candidate provenance via id() of each agent in the current
        # population. Survivors keep their lineage across generations;
        # refills receive a new lineage with parent_lineage_id pointing at
        # the survivor they were mutated from.
        self._origins: dict[int, _IndividualOrigin] = {}
        self._next_lineage_index = 0
        # Scores evaluated during the most recent step(), used to compute
        # the "improved vs previous generation median" flag on the next
        # emission. Seeded from a one-off root eval on the first step.
        self._last_scores: list[float] | None = None
        # Stable run_id pinned for the duration of this optimizer's life
        # so every step() and every nested agent invocation share one
        # identity in the dashboard. Lazily minted on first step() —
        # callers can also pin it explicitly via `session()`.
        self._algo_run_id: str | None = None

    def _discover_root(self) -> Agent[Any, Any]:
        for group in self.param_groups:
            for p in group.params:
                return p._agent()
        raise ValueError("EvoGradient got no parameters with attached agents")

    async def _attempt_mutate_and_build(
        self, parent: Agent[Any, Any], parent_lineage_id: str | None
    ) -> tuple[Agent[Any, Any], _IndividualOrigin] | None:
        before = _parameter_snapshot(self._root, parent)
        candidate = parent.clone()
        op = copy.deepcopy(self._rng.choice(self._mutations))
        op.apply(candidate)
        try:
            await candidate.abuild()
        except BuildError:
            op.undo(candidate)
            return None
        after = _parameter_snapshot(self._root, candidate)
        return candidate, _IndividualOrigin(
            op=op.name,
            path=getattr(op, "path", ""),
            lineage_id=self._new_lineage_id(),
            parent_lineage_id=parent_lineage_id,
            parameter_deltas=_parameter_deltas(before, after),
        )

    async def _fresh_individual(
        self, parent: Agent[Any, Any], parent_lineage_id: str | None
    ) -> Agent[Any, Any]:
        for _ in range(self._max_mutation_retries):
            outcome = await self._attempt_mutate_and_build(
                parent, parent_lineage_id
            )
            if outcome is not None:
                candidate, origin = outcome
                self._origins[id(candidate)] = origin
                return candidate
        warnings.warn(
            "EvoGradient: all mutation attempts failed to build after "
            f"{self._max_mutation_retries} retries; using unmutated clone",
            RuntimeWarning,
            stacklevel=2,
        )
        fallback = parent.clone()
        await fallback.abuild()
        self._origins[id(fallback)] = _IndividualOrigin(
            op=_IDENTITY_OP,
            path="",
            lineage_id=self._new_lineage_id(),
            parent_lineage_id=parent_lineage_id,
            parameter_deltas=[],
        )
        return fallback

    def _new_lineage_id(self) -> str:
        value = f"l{self._next_lineage_index:04d}"
        self._next_lineage_index += 1
        return value

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[str]:
        """Wrap a multi-step run with a stable run_id and `algo_end` emission.

        Every event emitted while the session is active — algorithm
        events from `step()` and nested agent events from each
        evaluation — shares one run_id, so the dashboard groups them as
        a single optimizer run. On exit, an `algo_end` event flips the
        run state to `ended`.
        """
        if self._algo_run_id is None:
            self._algo_run_id = uuid.uuid4().hex
        with _enter_algorithm_run(self._algo_run_id) as rid:
            try:
                yield rid
            finally:
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=type(self).__name__,
                    payload={"total_generations": self._generation},
                )

    async def step(self) -> None:
        if self._algo_run_id is None:
            self._algo_run_id = uuid.uuid4().hex
        with _enter_algorithm_run(self._algo_run_id):
            await self._step_body()

    async def _step_body(self) -> None:
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
                        self._fresh_individual(self._root, None)
                        for _ in range(self._population_size)
                    )
                )
            )

        reports = await asyncio.gather(
            *(
                self._evaluate_individual(i, a)
                for i, a in enumerate(self._population)
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
                *(
                    self._fresh_individual(p, self._origin_for(p).lineage_id)
                    for p in refill_parents
                )
            )
        )
        new_population = survivors + refills
        # Drop provenance for individuals that did not survive into the
        # next generation so the dict does not leak across many steps.
        kept_ids = {id(a) for a in new_population}
        self._origins = {
            k: v for k, v in self._origins.items() if k in kept_ids
        }
        self._population = new_population

        best = survivors[0]
        await self._write_back(best)
        self._last_scores = scores
        self._generation += 1

    async def _evaluate_individual(
        self, individual_id: int, individual: Agent[Any, Any]
    ) -> Any:
        origin = self._origin_for(individual)
        metadata = {
            "gen": self._generation,
            "gen_index": self._generation,
            "individual_id": individual_id,
            "lineage_id": origin.lineage_id,
            "parent_lineage_id": origin.parent_lineage_id,
            "operator": origin.op,
            "mutation_path": origin.path,
        }
        with _enter_algorithm_metadata(metadata):
            return await evaluate(individual, self._dataset, [self._metric])

    def _origin_for(self, individual: Agent[Any, Any]) -> _IndividualOrigin:
        origin = self._origins.get(id(individual))
        if origin is not None:
            return origin
        origin = _IndividualOrigin(
            op=_IDENTITY_OP,
            path="",
            lineage_id=self._new_lineage_id(),
            parent_lineage_id=None,
            parameter_deltas=[],
        )
        self._origins[id(individual)] = origin
        return origin

    async def _emit_algo_start(self) -> None:
        """Announce the run with the root agent's identity and Mermaid graph.

        The dashboard uses `root_path` to anchor mutation paths to graph
        node IDs (mutation paths are root-relative, but Mermaid IDs are
        rooted at the agent class name) and uses `graph_mermaid` to
        render the topology on the algorithm run's graph panel — agent
        evaluations during a run carry separate run_ids, so without
        this the algorithm run has no graph to render.
        """
        from operad.core.view import to_json, to_mermaid

        graph_mermaid: str | None = None
        graph_json: dict[str, Any] | None = None
        graph = getattr(self._root, "_graph", None)
        if graph is not None:
            try:
                graph_mermaid = to_mermaid(graph)
            except Exception:
                graph_mermaid = None
            try:
                graph_json = to_json(graph)
            except Exception:
                graph_json = None
        payload: dict[str, Any] = {
            "root_path": type(self._root).__name__,
            "population_size": self._population_size,
        }
        if graph_mermaid is not None:
            payload["graph_mermaid"] = graph_mermaid
        if graph_json is not None:
            payload["graph_json"] = graph_json
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
        origins = [self._origin_for(a) for a in population]
        ops = [o.op for o in origins]
        paths = [o.path for o in origins]
        improved = [s > median for s in scores]
        survivor_set = set(survivor_indices)
        selected_lineage_id = (
            origins[survivor_indices[0]].lineage_id if survivor_indices else None
        )
        individuals: list[dict[str, Any]] = [
            {
                "individual_id": i,
                "lineage_id": origins[i].lineage_id,
                "parent_lineage_id": origins[i].parent_lineage_id,
                "score": scores[i],
                "selected": i in survivor_set,
                "op": ops[i],
                "path": paths[i],
                "improved": bool(improved[i]),
                "parameter_deltas": origins[i].parameter_deltas,
            }
            for i in range(len(population))
        ]
        mutations: list[dict[str, Any]] = [
            {
                "individual_id": i,
                "lineage_id": origins[i].lineage_id,
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
            "selected_lineage_id": selected_lineage_id,
            "individuals": individuals,
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


def _parameter_snapshot(
    root: Agent[Any, Any], agent: Agent[Any, Any]
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for full_path, param in agent.named_parameters(recurse=True):
        agent_path, local_path = _split_agent_param_path(root, agent, full_path)
        snapshot[full_path] = {
            "agent_path": agent_path,
            "path": local_path,
            "type": type(param).__name__,
            "value": _json_safe(param.read()),
            "requires_grad": bool(param.requires_grad),
        }
    return snapshot


def _parameter_deltas(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for full_path in sorted(set(before) | set(after)):
        left = before.get(full_path)
        right = after.get(full_path)
        before_value = left.get("value") if left else None
        after_value = right.get("value") if right else None
        if _stable_json(before_value) == _stable_json(after_value):
            continue
        base = right or left
        if base is None:
            continue
        deltas.append(
            {
                "agent_path": base["agent_path"],
                "path": base["path"],
                "type": base["type"],
                "before": before_value,
                "after": after_value,
            }
        )
    return deltas


def _split_agent_param_path(
    root: Agent[Any, Any], agent: Agent[Any, Any], full_path: str
) -> tuple[str, str]:
    parts = full_path.split(".")
    node = agent
    agent_parts: list[str] = []
    while parts and parts[0] in node._children:
        name = parts.pop(0)
        agent_parts.append(name)
        node = node._children[name]
    return ".".join([type(root).__name__, *agent_parts]), ".".join(parts)


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))
