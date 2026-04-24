# 5 · 1 — `agent.auto_tune(dataset, metric)` one-liner

**Addresses.** A-3 — the north-star "agents optimize agents" vision
is technically reachable by calling `Evolutionary(...).run()` but
undiscoverable. A single `Agent.auto_tune(dataset, metric)` method
makes the story visible via `help(agent)`. See
[`../ISSUES.md`](../ISSUES.md) Group H.

**Depends on.** 4-4 (Evolutionary rollback) — auto_tune must not
leave the seed half-mutated if a generation fails. Phase 0 must be
merged (F-2 is a hard dependency for reliable cloning).

**Blocks.** 6-1 (agent_evolution demo) — the demo's one-liner.

---

## Required reading

- `operad/core/agent.py` — the `Agent` class and existing method
  surface. Pay attention to `clone`, `state`, `diff`, `build`.
- `operad/algorithms/evolutionary.py` — post-4-4 contract for
  `Evolutionary.run`.
- `operad/utils/ops.py` — `Op` subclasses. Post-4-4 they all have
  `undo()`.
- `operad/benchmark/evaluate.py` + `operad/benchmark/dataset.py` —
  `evaluate()`'s contract and `Dataset` coercion.
- `VISION.md` §7 (north-star #1: agents-optimizing-agents).

---

## Goal

Add `Agent.auto_tune(dataset, metric, ...)` that wraps the
`Evolutionary` algorithm with a sensible default mutation set and
returns a better agent. One-liner for users; delegates to existing
machinery.

## Scope

### New method on `Agent`

In `operad/core/agent.py`:

```python
async def auto_tune(
    self,
    dataset: Dataset[In, Out] | Iterable[tuple[In, Out]],
    metric: Metric,
    *,
    mutations: list[Op] | None = None,
    population_size: int = 8,
    generations: int = 4,
    rng: random.Random | None = None,
) -> "Agent[In, Out]":
    """Evolve a copy of this agent to improve `metric` on `dataset`.

    A thin wrapper around `operad.algorithms.Evolutionary`. Picks a
    reasonable default mutation set if `mutations` is None; clones
    the seed before evolving so `self` stays untouched.

    Returns the best agent found in the final generation.
    """
    from ..algorithms import Evolutionary
    from ..utils.ops import default_mutations

    seed = self.clone()  # do not mutate caller's agent
    ops = mutations if mutations is not None else default_mutations(seed)
    ds = list(dataset) if not hasattr(dataset, "hash_dataset") else dataset

    algo = Evolutionary(
        seed=seed,
        mutations=ops,
        metric=metric,
        dataset=ds,
        population_size=population_size,
        generations=generations,
        rng=rng,
    )
    return await algo.run()
```

### `default_mutations(agent)` helper

In `operad/utils/ops.py`:

```python
def default_mutations(agent: Agent[Any, Any]) -> list[Op]:
    """Return a starter set of `Op`s appropriate for the given agent.

    Heuristic: if the agent is a composite, build ops keyed to each
    child path. If it's a leaf, build ops keyed to the root path.

    The default set includes:
    - AppendRule: adds a generic constraint to the root's `rules`.
    - EditTask: rewrites the task to a slightly reworded variant.
    - SetRole (for leaves): rotates the persona.
    - Sampling temperature bump/drop via `SetTemperature`.
    """
    ...
```

A handful of `Op` subclasses may need to exist (most do already;
`SetTemperature` is easy if missing — setter mutates
`agent.config.sampling.temperature`).

Keep this helper **small and boring** — 8-12 ops maximum. It's not
meant to be exhaustive; it's a one-liner's default. Power users
supply their own `mutations=[...]` list.

### Public export

No change to package `__all__` — `agent.auto_tune(...)` is discoverable
via method lookup.

### Docs / docstring

Make the docstring feature the one-liner usage and reference the
Evolutionary algorithm + the default mutation set. Include a "for
production" note pointing at `Evolutionary` directly for custom
`mutations=` / `rng=` / observers.

---

## Verification

- Unit test with `FakeLeaf` seeds, deterministic `rng`, and a metric
  that rewards more rules (same shape as
  `examples/evolutionary_demo.py::RuleCountMetric`):
  - `await seed.auto_tune(ds, metric, generations=2, population_size=4)`
    returns an agent whose `metric`-score on `ds` is > seed's score.
  - `seed` is untouched (`seed.state() == before`).
- Unit test: default mutations cover at least one rule-append, one
  task-edit, one temperature-bump.
- Integration test with a small `_DefaultLeaf` + `FakeLeaf` mix and a
  stub metric: end-to-end completes offline.
- `scripts/verify.sh` green.

---

## Out of scope

- A discovery mechanism that scans an agent's structure and builds
  mutations for every leaf/composite automatically. Users who want
  that provide `mutations=` manually; the default set is
  intentionally shallow.
- Mutation crossover / recombination. `Evolutionary` today does
  mutation-only; crossover is a separate algorithm brief when we
  want it.
- Dashboard integration. The algorithm events from 4-1 fire
  automatically; auto_tune doesn't need to do anything extra.

---

## Design notes

- Keep the method body short — it's literally wrapper glue. The
  heavy lifting lives in `Evolutionary` and the Op system.
- Do not cache `default_mutations(agent)` — call it fresh each time
  so instance-specific paths resolve correctly.
- If the target agent is built, `clone()` (post-F-2) drops the
  strands wiring; `Evolutionary` rebuilds its population on each
  generation. No extra handling needed here.
