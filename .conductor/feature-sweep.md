# Feature · `Sweep` — parameter-grid algorithm

A new algorithm in `operad/algorithms/sweep.py` that takes a seed
agent plus a set of parameter values (not single values) and
instantiates / builds / runs the Cartesian product in parallel.

**Covers Part-3 item.** #4, redesigned per feedback — it's an
algorithm, not a free function; inputs are parameter sets, not
single values; everything runs in parallel.

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §4 (algorithms are not
agents), and:
- `.conductor/1-B-agent-state.md` — `Agent.clone()` is the primitive
  Sweep uses to spawn variants.
- `.conductor/feature-mutation-ops.md` — parameter specification
  reuses the `Op` types from `utils/ops.py`.
- `.conductor/2-F-algorithms.md` — other algorithms' shape for
  consistency (`BestOfN`, `Evolutionary`).

---

## Proposal sketch

### Shape

```python
class Sweep(Generic[In, Out]):
    """Cartesian parameter sweep: build one agent per combination.

    Parameters are specified as a dict from dotted attribute paths
    (or Op factories — see below) to a list of values. Each
    combination produces a cloned, re-parameterised, rebuilt agent
    ready to run.
    """

    def __init__(
        self,
        seed: Agent[In, Out],
        parameters: dict[str, list[Any]],
        *,
        concurrency: int = 4,
    ) -> None: ...

    async def run(self, x: In) -> SweepReport[In, Out]: ...
```

`parameters` example:

```python
{
    "reasoner.task": [
        "Think step by step, then answer.",
        "Be terse and commit to an answer.",
    ],
    "reasoner.config.temperature": [0.2, 0.5, 0.8],
}
```

→ 2 × 3 = 6 combinations.

### Return shape

```python
class SweepCell(BaseModel, Generic[In, Out]):
    parameters: dict[str, Any]       # one combination
    output: OperadOutput[Out]        # feature-operad-output.md

class SweepReport(BaseModel, Generic[In, Out]):
    cells: list[SweepCell[In, Out]]
```

### Implementation shape

```python
async def run(self, x: In) -> SweepReport[In, Out]:
    combos = list(_cartesian(self.parameters))
    agents = [self._apply(self.seed.clone(), c) for c in combos]
    await asyncio.gather(*(a.abuild() for a in agents))
    sem = asyncio.Semaphore(self.concurrency)
    outputs = await asyncio.gather(
        *(_bounded(sem, a(x)) for a in agents)
    )
    return SweepReport(cells=[...])
```

### Using `Op` objects as parameters (investigate)

Investigate whether `parameters` should also accept `Op` instances
from `feature-mutation-ops.md`:

```python
from operad.utils.ops import SetTemperature, AppendRule

parameters = {
    SetTemperature(path="reasoner"): [0.2, 0.5, 0.8],
    AppendRule(path="reasoner"): ["Be terse.", "Be thorough."],
}
```

This generalises the "dotted path → value" idea without special
casing. Decide after prototyping; dotted paths for simple cases may
be enough.

---

## Research directions

- **Dotted-path resolution.** Need a helper to walk
  `agent.reasoner.config.temperature` via attribute access. Write
  this once in `operad/utils/paths.py` and reuse in Evolutionary,
  Sweep, and `feature-agent-introspection.md`.
- **Pairing vs. Cartesian.** Some users may want *zip* semantics
  (pair parameters row-wise, not Cartesian). Decide the default
  (Cartesian) and document; a `zip=True` flag is a small follow-up.
- **Empty or single-value axes.** `parameters={"a.b": []}` → zero
  combinations, run returns an empty report. `parameters={}` → one
  combination = the seed unchanged. Verify both are sensible.
- **Concurrency discipline.** Sweep's `concurrency` bound is
  per-agent-call. The slot registry already bounds per-backend.
  Think about what happens when both limits are in play.
- **Integration with `evaluate`.** A natural extension:
  `Sweep.evaluate(dataset, metrics)` that returns a cell×metric
  grid. Investigate and decide whether to include in v1 or defer.

---

## Integration & compatibility requirements

- **Hard dependency on `Agent.clone()`** (Stream B). Do not start
  until Stream B is merged.
- **Do not modify the seed.** Every cell works on a clone. Assert in
  tests: after `Sweep.run`, `seed.state()` is unchanged.
- **Output shape uses `OperadOutput`.** Coordinate with the feature
  that ships it (`feature-operad-output.md`).
- **Dotted-path helper lives in `operad/utils/paths.py`** so Sweep,
  Evolutionary, and Ops share it. Do not duplicate.
- **Type safety.** `SweepReport[In, Out]` is a generic Pydantic
  model; test that it round-trips via `model_dump_json`.

---

## Acceptance

- `uv run pytest tests/` green.
- `tests/test_sweep.py`: a 2×3 parameter grid produces exactly 6
  `SweepCell`s with distinct parameter combinations.
- `tests/test_sweep.py`: seed is unchanged after `run()`.
- `examples/sweep_demo.py` runs offline (FakeLeaf-backed) against a
  4-cell grid.

---

## Watch-outs

- Do NOT let Sweep take a dataset in v1 — that's what `evaluate()`
  is for; combine them only once both are stable.
- Asyncio.gather without concurrency bounds will stampede local
  endpoints. Bound it.
- Cartesian product grows multiplicatively — refuse to start if
  combinations exceed a configurable cap (default 1024) with a
  clear message.
- Do NOT reach into `_children` private attributes to apply
  parameters. Use the dotted-path helper or public `state()`/`load_state()`.
