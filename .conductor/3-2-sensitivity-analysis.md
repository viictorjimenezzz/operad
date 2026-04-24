# 3 · 2 — `benchmark.sensitivity` — rank parameters by ΔΜetric

**Addresses.** R-research-5 (sensitivity analysis: how much does each
parameter move the metric?).

**Depends on.**
- 2-5 (benchmark foundation — `Dataset`, `evaluate`, `AggregatedMetric`).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (reproducibility → experimentation).
- `operad/algorithms/sweep.py` — `Sweep`, `SweepCell`, `SweepReport`.
  `sensitivity` uses `Sweep` internally for the parameter grid
  realisation.
- `operad/benchmark/` (post-2-5) — `Dataset`, `evaluate`,
  `AggregatedMetric`.
- `operad/utils/paths.py` — `set_path` for dotted-path mutation of a
  clone.

---

## Proposal

`sensitivity(agent, dataset, metric, *, perturbations=None)` perturbs
selected configuration knobs, re-evaluates the agent on the dataset
under each perturbation, and returns a ranked `SensitivityReport`.

### Default perturbation set

When `perturbations=None`, probe the sampling knobs that are most
likely to move behaviour:

```python
DEFAULT_PERTURBATIONS = {
    "config.sampling.temperature": [-0.2, +0.2],   # relative (fractional)
    "config.sampling.top_p":       [-0.1, +0.1],   # absolute delta on (0, 1]
    "config.sampling.top_k":       [-10, +10],     # absolute delta, clamped ≥ 1
    "config.sampling.max_tokens":  [-256, +256],   # absolute delta
}
```

(Paths use post-2-3-4 nested Configuration layout. If 3-4 lands after
3-2, the paths collapse to `config.temperature` etc. — this brief
must land on the *pre-3-4* flat layout or the dotted paths above need
to match whichever shape is current at merge time.)

Note: **3-2 does NOT depend on 3-4.** Use the *current flat
Configuration paths* (`config.temperature`, `config.top_p`, etc.)
unless 3-4 has merged first. If the layout changes later, the paths
update in lockstep — not this PR's problem.

### Custom perturbations

```python
perturbations: dict[str, list[Any]] = {
    "config.temperature": [0.0, 0.3, 0.7, 1.0],   # absolute values
    "rules": [[...], [...]],                       # swap whole rule lists
}
```

Callers can provide absolute values (a list) or relative deltas (the
default-set form above using fractional / absolute deltas). This PR's
API is **absolute values only** to keep the semantics unambiguous:

```python
perturbations = {
    "config.temperature": [0.5, 0.7, 0.9],   # try these three
}
```

The default perturbation set in code is still dict-valued; convert
relative deltas to absolute values internally by reading the agent's
current Configuration.

### API

```python
# operad/benchmark/sensitivity.py

from typing import Any, Generic
from pydantic import BaseModel, Field

from ..algorithms.sweep import Sweep
from ..core.agent import Agent
from ..metrics.base import Metric
from .dataset import Dataset
from .aggregated import AggregatedMetric, Reducer


class SensitivityCell(BaseModel):
    """One (parameter-path, value) assignment with its aggregated metric."""
    parameter: str
    value: Any
    score: float


class SensitivityReport(BaseModel):
    """Cells sorted by |delta| descending; baseline at index 0."""
    baseline: float
    cells: list[SensitivityCell] = Field(default_factory=list)
    ranking: list[tuple[str, float]] = Field(default_factory=list)
    # ranking: (parameter_path, max_abs_delta_across_values_for_that_path)


async def sensitivity(
    agent: Agent,
    dataset: Dataset,
    metric: Metric,
    *,
    perturbations: dict[str, list[Any]] | None = None,
    reducer: Reducer = "mean",
    concurrency: int = 4,
) -> SensitivityReport: ...
```

### Algorithm

1. Compute `baseline = await _evaluate_one(agent, dataset, metric)` —
   the aggregated metric under the agent's current configuration.
2. For each `(path, values)` in `perturbations`:
   - Use `Sweep` with `{path: values}` to spawn one clone per value
     (Sweep handles dotted-path mutation + rebuild).
   - Treat each clone as one dataset evaluation; collect aggregated
     score per value.
3. Compute per-path `max_abs_delta = max(|score - baseline|)` across
   all values for that path.
4. Rank paths by `max_abs_delta` descending → `ranking`.
5. Return the report.

Under the hood, Sweep runs clones in parallel up to `concurrency`. A
`perturbations` dict with K paths × V values per path produces K × V
full dataset evaluations, each costing `|dataset|` forwards. Bound
carefully on live backends.

### Re-export

```python
# operad/benchmark/__init__.py
from .sensitivity import sensitivity, SensitivityReport, SensitivityCell
__all__ = [..., "sensitivity", "SensitivityReport", "SensitivityCell"]
```

Not promoted to `operad.__all__`.

---

## Required tests

`tests/test_benchmark_sensitivity.py` (new):

1. **Baseline computed.** `FakeLeaf` returns a deterministic answer;
   `sensitivity(agent, ds, metric)` returns a report where
   `report.baseline` matches `evaluate(agent, ds, [metric]).summary[
   metric.name]`.
2. **Perturbation cells present.** With explicit
   `perturbations={"config.temperature": [0.1, 0.9]}`, the report
   has at least two `SensitivityCell`s for that path.
3. **Ranking order.** Parameter `A` whose perturbations produce
   metric range [0.8, 0.82] (small delta) ranks below parameter
   `B` whose perturbations produce range [0.2, 0.9] (large delta).
4. **Default perturbations.** Calling with `perturbations=None`
   probes at least the sampling axes; the default set maps to
   absolute values derived from the agent's current config.
5. **Concurrency bound honoured.** Set `concurrency=1`; check via a
   counter that no two evaluations run in parallel. (Use a shared
   state counter incremented in the FakeLeaf's `forward`.)
6. **Agent mutated back to baseline.** After `sensitivity` returns,
   the caller's original agent instance has the unchanged baseline
   configuration (Sweep clones, doesn't mutate).

Offline; `FakeLeaf` + deterministic metric. No cassettes needed.

---

## Scope

**New files.**
- `operad/benchmark/sensitivity.py`.
- `tests/test_benchmark_sensitivity.py`.

**Edited files.**
- `operad/benchmark/__init__.py` — re-export.

**Must NOT touch.**
- `operad/algorithms/sweep.py` — consume only.
- `operad/core/`, `operad/runtime/`, `operad/metrics/`,
  `operad/agents/`.
- Other benchmark files.

---

## Acceptance

- `uv run pytest tests/test_benchmark_sensitivity.py` green.
- `uv run pytest tests/` green.
- `from operad.benchmark import sensitivity, SensitivityReport,
  SensitivityCell` works.

---

## Watch-outs

- **Cost blowup.** `K` paths × `V` values × `|dataset|` forwards per
  evaluation. A 4-path × 3-value sweep on a 20-row dataset is 240
  calls. Document the cost model in the function docstring and hard-
  cap via `Sweep.max_combinations` (the underlying `Sweep` already
  does this; surface the same cap as a `max_combinations` kwarg on
  `sensitivity`).
- **Absolute vs relative.** The public API accepts absolute values
  only, to remove ambiguity. The *default* perturbation set is
  generated from the agent's current config plus relative deltas,
  but that generation is internal.
- **Dotted paths must be valid.** `set_path(clone, path, value)`
  raises on invalid paths. Surface that cleanly — wrap Sweep's
  errors with a friendlier message naming the bad path and the
  perturbation dict key.
- **Sweep + build().** Each clone needs `.build()` before evaluation.
  `Sweep` does that already; `sensitivity` must not double-build.
- **Deterministic ordering.** The final `ranking` tie-breaks on the
  parameter path string for stability across runs. Otherwise a sweep
  with identical deltas returns nondeterministic order and tests
  flake.
- **Metric side effects.** Metric implementations must be
  side-effect-free (no LLM call state accumulation across evaluation
  rounds). Document for users bringing `RubricCritic` — it may be
  fine, but re-entry across clones should be verified.
- **Baseline included in cells or separate?** Separate. `baseline`
  is a named field; cells carry only perturbed values. This keeps
  the ranking math clean (`delta = cell.score - report.baseline`).
