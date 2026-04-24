# 2 · 5 — Benchmark foundation (`Entry` / `Dataset` / `AggregatedMetric`)

**Addresses.** User-added foundation. Enables Wave 3 (`3-1-regression-check`,
`3-2-sensitivity-analysis`, `3-3-experiment-primitive`).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (reproducibility; runs as artefacts).
- `operad/datasets.py` — current `Dataset[In, Out]` (`list[tuple[In, Out]]`).
  This file is **deleted** as part of this PR.
- `operad/eval.py` — current `evaluate(agent, dataset, metrics)` +
  `EvalReport`. Moves to `operad/benchmark/evaluate.py`.
- `operad/metrics/base.py` — `Metric` protocol (not touched by this PR).
- `operad/__init__.py` — current re-exports for `Dataset`, `evaluate`,
  `EvalReport`.

---

## Proposal

Today's `Dataset[In, Out]` is a list of `(input, expected)` tuples — fine
for a one-off eval, but missing the hooks downstream work (3-1 regression,
3-2 sensitivity, 3-3 experiment) will want:

- per-entry `metric` override (so one dataset can carry heterogeneous
  scoring policies per row);
- a clear container (`Entry`) to hang metadata off without adding
  positional arguments;
- a way to summarise a list of per-row scores with a named reducer
  (`AggregatedMetric`) rather than always reaching into `summary[name]`.

Introduce a new top-level package `operad/benchmark/` that owns these
pieces, absorbs `datasets.py` + `eval.py`, and becomes the home for Wave-3
additions.

### Layout

```
operad/benchmark/
    __init__.py        # re-exports Entry, Dataset, AggregatedMetric, evaluate, EvalReport
    entry.py           # Entry[In, Out]
    dataset.py         # Dataset[In, Out] built on list[Entry[In, Out]]
    aggregated.py      # AggregatedMetric
    evaluate.py        # evaluate() + EvalReport (moved from operad/eval.py)
```

### `Entry`

```python
# operad/benchmark/entry.py
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field
from ..metrics.base import Metric

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Entry(BaseModel, Generic[In, Out]):
    """One row in a benchmark dataset.

    `expected_output` is optional — some datasets only have inputs
    (for sensitivity analysis, human eval, etc.). `metric` is an
    optional per-row override that the evaluator uses when the global
    metric list is left empty.
    """
    input: In
    expected_output: Out | None = None
    metric: Metric | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

### `Dataset`

Same public surface as today's `operad.Dataset` (iteration, `len`,
indexing, `hash_dataset`, `save`, `load`), but internally `list[Entry]`.
NDJSON now encodes `metric` as an optional string (the metric's `name`;
rehydration must accept a `metric_registry: dict[str, Metric]` to recover
the actual callable, or leaves it `None` when the caller doesn't care).

```python
# operad/benchmark/dataset.py
class Dataset(Generic[In, Out]):
    def __init__(
        self,
        entries: Iterable[Entry[In, Out]] | Iterable[tuple[In, Out]],
        *,
        name: str = "",
        version: str = "",
    ) -> None:
        self._entries: list[Entry[In, Out]] = [
            e if isinstance(e, Entry) else Entry(input=e[0], expected_output=e[1])
            for e in entries
        ]
        ...

    @property
    def hash_dataset(self) -> str:
        """Stable 16-hex-char content hash over entries + name + version."""
        # includes metric.name when present
```

NDJSON line format:

```json
{"input": {...}, "expected_output": {...}, "metric": "exact_match"}
```

When `expected_output` is absent the key is omitted; when `metric` is
absent the key is omitted. The hash includes these keys in a canonical
order so identical content always hashes identically.

### `AggregatedMetric`

```python
# operad/benchmark/aggregated.py
from typing import Literal

Reducer = Literal["mean", "median", "min", "max", "sum"]


class AggregatedMetric:
    """Combine a list of per-row scores into a single scalar.

    Stateless; cheap to construct. Use it when downstream callers
    (3-1 regression, 3-2 sensitivity) need one summary number per
    metric rather than the full per-row vector.
    """

    def __init__(self, *, reducer: Reducer = "mean", name: str = "") -> None:
        self.reducer: Reducer = reducer
        self.name = name or reducer

    def aggregate(self, scores: list[float]) -> float:
        # ignore NaN; if all NaN return NaN; else apply reducer
        ...
```

### `evaluate` (moved)

Direct lift-and-shift of `operad/eval.py` into
`operad/benchmark/evaluate.py`, with two changes:

1. Iterate over `Dataset._entries` (or accept a raw `Iterable[Entry]`).
2. When `metrics=None`, compose a per-row metric list from each
   `Entry.metric` (skipping rows with no metric and no global default).
   When `metrics` is provided, it overrides per-entry policies entirely
   (existing behaviour).

Function signature:

```python
async def evaluate(
    agent: Agent[In, Out],
    dataset: Dataset[In, Out] | Iterable[Entry[In, Out]],
    metrics: list[Metric] | None = None,
    *,
    concurrency: int = 4,
) -> EvalReport: ...
```

`EvalReport` unchanged in shape (rows/summary/hashes) — the per-row
dict now also stores `"metric"` when the policy came from the entry.

### `operad/__init__.py`

Top-level re-exports updated: `Dataset`, `evaluate`, `EvalReport` now
come from `operad.benchmark` (drop the old `operad.datasets` /
`operad.eval` imports, which are being deleted).

`Entry` and `AggregatedMetric` do NOT graduate to the top-level list —
they live at `operad.benchmark.Entry`, `operad.benchmark.AggregatedMetric`
(1-1 capped the top-level surface at ~18 names).

---

## Required tests

`tests/test_benchmark.py` (new):

1. **Entry round-trip NDJSON.** Build a `Dataset` of three `Entry`
   rows, `.save(tmp_path / "d.ndjson")`, `.load(...)` back. Entries
   restore with inputs, expected outputs, and `metric=None`
   (unless a registry is supplied).
2. **Dataset hash stable + sensitive.** Two datasets with the same
   rows + name + version hash equal; mutating any field changes the
   hash. Per-entry metric name contributes.
3. **Evaluate with per-entry metrics.** A dataset with rows tagged
   `metric=ExactMatch()` and `metric=Contains()`; call
   `await evaluate(agent, ds)` with `metrics=None`; report rows show
   each row's score under the chosen metric key.
4. **Evaluate global-override.** Same dataset, explicit
   `metrics=[ExactMatch()]`; per-entry policies are ignored, every
   row carries the ExactMatch score.
5. **AggregatedMetric reducers.** `AggregatedMetric("mean").aggregate(
   [0.0, 1.0, 0.5]) == 0.5`; `"median"` → 0.5; `"min"` → 0.0;
   `"max"` → 1.0; `"sum"` → 1.5. NaN-filtering: single NaN is
   ignored; all-NaN returns NaN.
6. **Top-level import.** `from operad import Dataset, evaluate,
   EvalReport` works; `from operad.benchmark import Entry,
   AggregatedMetric` works; `from operad.datasets import Dataset`
   raises `ModuleNotFoundError`.

Retire `tests/test_datasets.py` (migrate its assertions to
`test_benchmark.py` under the new shape).

---

## Scope

**New files.**
- `operad/benchmark/__init__.py`
- `operad/benchmark/entry.py`
- `operad/benchmark/dataset.py`
- `operad/benchmark/aggregated.py`
- `operad/benchmark/evaluate.py`
- `tests/test_benchmark.py`

**Deleted files.**
- `operad/datasets.py` (absorbed into `operad/benchmark/dataset.py`).
- `operad/eval.py` (absorbed into `operad/benchmark/evaluate.py`).
- `tests/test_datasets.py` (replaced by `tests/test_benchmark.py`).
- `tests/test_eval.py` if its assertions all move.

**Edited files.**
- `operad/__init__.py` — import `Dataset`, `evaluate`, `EvalReport` from
  `operad.benchmark`; drop stale imports.
- `operad/runtime/replay.py` — imports `EvalReport` from
  `..benchmark.evaluate` (was `..eval`).
- `demo.py`, any example that imports `operad.datasets` or
  `operad.eval` directly (grep and migrate).

**Must NOT touch.**
- `operad/metrics/` — the `Metric` protocol stays put; `AggregatedMetric`
  is a new concept that *composes* metric scores, not a replacement.
- `operad/core/` — entirely.
- Any other Wave-2 file.

---

## Acceptance

- `uv run pytest tests/` green.
- `uv run python -c "import operad; print(operad.Dataset, operad.evaluate)"`
  works.
- `uv run python -c "from operad.benchmark import Entry, AggregatedMetric"`
  works.
- `uv run python -c "import operad.datasets"` raises `ModuleNotFoundError`.
- `uv run --extra observers python demo.py` runs.

---

## Watch-outs

- **`Metric` is a Protocol, not a BaseModel.** `Entry.metric: Metric | None`
  requires `ConfigDict(arbitrary_types_allowed=True)`. Serialising a
  Protocol-typed attribute to NDJSON cannot round-trip the callable —
  only the `name`. Document this explicitly: `load()` takes an optional
  `metric_registry: dict[str, Metric]` and looks up by name. Missing
  keys raise `KeyError` (loud, not silent).
- **Old `Dataset.__init__(list[tuple])` still works.** The new `Dataset`
  accepts either `Iterable[Entry]` or `Iterable[tuple[In, Out]]` in its
  constructor for ergonomic parity. The stored form is always `list[
  Entry]`.
- **`hash_dataset` collision domain.** The old `Dataset` hashed
  `{name, version, rows: [{input, output}, ...]}`. The new one must
  hash an equivalent canonical form *when no per-row metric is set*, so
  cassette replays or stored `EvalReport.hash_dataset` values against
  a pre-2-5 snapshot still match. Use a canonical per-row form:
  ```python
  {"input": ..., "expected_output": ...}
  ```
  and only add `"metric": name` when non-null. This keeps the hash
  stable across the refactor for datasets without per-entry metrics.
- **`operad/eval.py` circular import avoidance.** After the move,
  `operad.runtime.replay` imports `EvalReport` from
  `operad.benchmark.evaluate`; `operad.benchmark.evaluate` imports
  `Agent` from `operad.core.agent`. No cycle — confirm with a fresh
  `python -c "import operad.runtime.replay"` after the move.
- **Demo and examples.** `examples/eval_demo.py` (if present) and
  `demo.py` must switch imports in this PR so `uv run python demo.py`
  stays green.
- **Top-level surface.** `Dataset` and `evaluate` remain in
  `operad.__all__`; `Entry` and `AggregatedMetric` do NOT. Reason: the
  top-level stratification cap (R4 in 1-1) was 18 names; per-row
  benchmark primitives live under `operad.benchmark`.
