# 3 · 1 — `benchmark.regression_check` — gold trace or dataset comparison

**Addresses.** R-research-3 (regression check: detect when an agent
change moves behaviour relative to a gold baseline).

**Depends on.**
- 2-5 (benchmark foundation — `Entry`, `Dataset`, `AggregatedMetric`,
  `evaluate`).
- 2-1 (`hash_content` used for invariant check in the report).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (runs-as-artefacts, gold-trace
  regression as the natural CI hook).
- `operad/benchmark/` (created by 2-5) — `Entry`, `Dataset`,
  `AggregatedMetric`, `evaluate`.
- `operad/runtime/trace.py` — `Trace`, `TraceStep`.
- `operad/runtime/trace_diff.py` — `trace_diff(prev, next)`,
  `TraceStepDelta`.
- `operad/metrics/base.py` — `Metric` protocol.

---

## Proposal

Add a single function `regression_check` that accepts *either* a gold
`Trace` *or* a `Dataset` and returns a structured `RegressionReport`.
The idea is the same in both cases — "did behaviour move?" — but the
signal is different:

- **Trace mode.** Gold is a previously captured run. For each step in
  the replay run, use `trace_diff` to compare; flag any step with
  `status != "unchanged"`. Report `ok = True` iff every step matched
  under the configured equivalence (exact, hash-only, or metric-based).
- **Dataset mode.** Gold is a `Dataset` with `Entry.expected_output`
  populated. Run `evaluate(agent, dataset, metrics)`; compute the
  aggregated mean (via `AggregatedMetric`); report `ok = True` iff
  mean ≥ `threshold`.

One entry point, two branches.

### API

```python
# operad/benchmark/regression.py

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

from ..core.agent import Agent
from ..metrics.base import Metric
from ..runtime.trace import Trace
from ..runtime.trace_diff import trace_diff, TraceDiff
from .dataset import Dataset
from .entry import Entry
from .evaluate import evaluate, EvalReport
from .aggregated import AggregatedMetric, Reducer


class RegressionReport(BaseModel):
    """Summary of a regression check.

    `ok` is the bottom-line pass/fail. `mode` is which branch ran.
    `trace_diff` is populated in trace mode, `eval_report` in dataset
    mode. `agent_hash_content` snapshots the agent identity.
    """

    ok: bool
    mode: Literal["trace", "dataset"]
    trace_diff: TraceDiff | None = None
    eval_report: EvalReport | None = None
    threshold: float | None = None
    actual: float | None = None
    agent_hash_content: str = ""


async def regression_check(
    agent: Agent,
    gold: Trace | Dataset | str | Path,
    *,
    metrics: list[Metric] | None = None,
    threshold: float = 1.0,
    reducer: Reducer = "mean",
    equivalence: Literal["exact", "hash", "metric"] = "hash",
) -> RegressionReport: ...
```

Gold resolution:

- `Trace` instance → trace mode.
- `Dataset` instance → dataset mode.
- `str`/`Path` ending in `.ndjson` or `.jsonl` → `Dataset.load`.
- `str`/`Path` ending in `.json` → `Trace.load`.
- Anything else → `ValueError`.

### Trace-mode equivalence policies

- `"exact"` — step status must be `"unchanged"`; any hash delta fails.
- `"hash"` (default) — step with `hash_output_schema` drift fails
  (uses 2-3's drift detection); `hash_prompt`/`hash_input` changes are
  tolerated; `response_dump` must match exactly.
- `"metric"` — require `metrics` to be supplied; per-step, score
  `prev.response` vs `next.response` via each metric and assert
  `score >= threshold`.

### Dataset-mode behaviour

Under dataset mode, the report's `actual` is
`AggregatedMetric(reducer).aggregate(
  [row[m.name] for row in eval_report.rows])` for a single metric. If
multiple metrics are supplied, take the min of their aggregated
scores (pessimistic). `ok = actual >= threshold`.

### Relationship to existing `trace_diff` / `evaluate`

`regression_check` is a thin façade — it runs the underlying primitive
and layers a pass/fail decision on top. No new diffing logic in this
PR; just orchestration.

### Re-export

```python
# operad/benchmark/__init__.py
from .regression import regression_check, RegressionReport
__all__ = [..., "regression_check", "RegressionReport"]
```

Not promoted to `operad.__all__` (top-level cap stays at ~18).

---

## Required tests

`tests/test_benchmark_regression.py` (new):

1. **Trace mode, no drift.** Capture a trace of a FakeLeaf on input
   X; replay against the same agent; `regression_check(agent, gold)`
   returns `ok=True`, `mode="trace"`, every delta `"unchanged"`.
2. **Trace mode, prompt drift, hash equivalence.** Mutate the FakeLeaf's
   role (changes `hash_prompt`); run replay; delta reports
   `status="changed"`; `ok=False` under `equivalence="hash"`.
3. **Trace mode, metric equivalence.** Two traces with different
   `response_dump` but the metric scores them as equivalent (e.g.
   both pass a deterministic ExactMatch because only formatting
   differs); `ok=True` under `equivalence="metric"`.
4. **Dataset mode, passing.** `Dataset` of 3 entries with
   `expected_output`; FakeLeaf returns correct answers; `ExactMatch`
   metric; `threshold=1.0` → `ok=True`, `actual=1.0`.
5. **Dataset mode, failing.** One answer wrong (2/3 correct);
   `threshold=1.0` → `ok=False`, `actual≈0.667`.
6. **Gold as path.** Save a trace to `tmp_path/"gold.json"`; pass the
   path; same behaviour as passing the `Trace` object.
7. **Gold type mismatch.** Passing a `Dataset` with
   `equivalence="hash"` raises `ValueError` (hash equivalence is
   trace-only).
8. **`agent_hash_content` recorded.** Report's `agent_hash_content`
   matches `agent.hash_content` at call time.

All tests offline; `FakeLeaf` + deterministic metrics.

---

## Scope

**New files.**
- `operad/benchmark/regression.py`.
- `tests/test_benchmark_regression.py`.

**Edited files.**
- `operad/benchmark/__init__.py` — re-export `regression_check`,
  `RegressionReport`.

**Must NOT touch.**
- `operad/runtime/trace.py`, `operad/runtime/trace_diff.py` — consume
  only.
- `operad/benchmark/evaluate.py`, `.dataset.py`, `.entry.py`,
  `.aggregated.py` — use as imported; no changes.
- `operad/core/`, `operad/metrics/`, `operad/agents/`.

---

## Acceptance

- `uv run pytest tests/test_benchmark_regression.py` green.
- `uv run pytest tests/` green.
- `from operad.benchmark import regression_check, RegressionReport`
  works.

---

## Watch-outs

- **Hash-based equivalence vs metric-based.** Make the `equivalence`
  choice explicit per call; a silent default to hash-mode produces
  false negatives when the prompt template changed but semantic
  output is unchanged. Document the trade-off in the function
  docstring: `"hash"` is the CI default (fast, deterministic);
  `"metric"` is for research where you tolerate surface variance.
- **`trace_diff` step matching.** `trace_diff` matches by exact
  `agent_path`; composite fan-out (e.g. `BestOfN`) produces
  duplicates matched in order. That's fine for regression but means
  an added/removed step in a fan-out child shows up as a
  `status="added"` or `"removed"` entry. `equivalence="exact"` will
  flag those; `equivalence="hash"` also flags them. Document.
- **`agent_hash_content` is a snapshot.** Computed at call time,
  baked into the report for audit. Not used for equivalence — it's
  only a fingerprint for "what agent produced this report."
- **Async metric evaluation.** `equivalence="metric"` must iterate
  steps and await `metric.score`. Use `asyncio.gather` across steps
  for speed; keep per-metric order stable.
- **`Dataset` with no `expected_output`.** Dataset-mode regression
  requires `expected_output` on each entry. If missing, raise a
  `ValueError` at call time — don't silently compare empty values.
- **Threshold semantics.** `threshold=1.0` is "perfect match
  required"; typical CI hook. Users lowering it to 0.95 sacrifice
  strictness for flakiness tolerance — document clearly.
- **No backward compat to `operad.eval.evaluate`.** This PR assumes
  `operad.benchmark.evaluate` (from 2-5) is the only evaluator.
- **Return type.** `RegressionReport` is a Pydantic model so it's
  serialisable to JSON for CI artefact storage. Include it in the
  top-level `operad.benchmark` namespace for discoverability.
