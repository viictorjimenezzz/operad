# 4-2 — Benchmark consumer

> **Iteration**: 4 of 4. **Parallel slot**: 2.
> **Owns**: a NEW `/benchmarks` route, ingest endpoint, page, and
> consumer components.
> **Forbidden**: existing layouts/components.

## Problem

`examples/benchmark/run.py` already produces a structured JSON report
comparing TGD vs Momentum vs EvoGradient vs OPRO vs APE vs Sweep
across three tasks (intent classification, summarization, tool-call
selection), each across three seeds. The README says "fill in the
results table" — meaning today the comparison story is **hand-written
markdown**.

The dashboard should be the canonical home for this. A user runs
`uv run python examples/benchmark/run.py --out report.json`, and the
dashboard has a `/benchmarks` page that ingests the report and
renders:

- Per-task × method matrix (mean ± stddev).
- Cost-vs-metric scatter across all (task, method, seed) cells.
- A "freeze and tag" button so future runs can show ∆ vs baseline.

## Scope

### Owned files

- New: `apps/dashboard/operad_dashboard/routes/benchmarks.py` — accepts
  ingest POSTs, stores reports, exposes a list endpoint.
- New: `apps/dashboard/operad_dashboard/benchmark_store.py` — small
  in-memory (or SQLite via 4-4) store for benchmark reports.
- New: `apps/frontend/src/dashboard/pages/BenchmarksPage.tsx`
- New: `apps/frontend/src/dashboard/pages/BenchmarkDetailPage.tsx`
- New: `apps/frontend/src/shared/charts/benchmark-matrix.tsx`
- New: `apps/frontend/src/shared/charts/method-leaderboard.tsx`
- `apps/frontend/src/dashboard/routes.tsx` — register two new routes
  (`/benchmarks` and `/benchmarks/:id`). Coordinate with 4-1, 4-3.
- Optional: extend `examples/benchmark/run.py` to POST its report on
  completion if a `--dashboard` flag is set. Out of scope if it
  complicates the bench script — better to ingest manually.
- Tests.

### Forbidden files

- Existing layouts/components.
- Run registry code (`runs.py` etc.) — benchmarks are a separate
  data domain.

## Direction

### Backend: `/benchmarks` API

```
POST /benchmarks/_ingest
  body: <JSON report from examples/benchmark/run.py --out>
  returns: {id: str}

GET  /benchmarks
  returns: [{id, name, created_at, n_tasks, n_methods, summary}]

GET  /benchmarks/{id}
  returns: full report

POST /benchmarks/{id}/tag
  body: {tag: "baseline-v1"}
  returns: {ok: true}

DELETE /benchmarks/{id}
```

### Report schema

Read `examples/benchmark/run.py` to learn the shape it produces. Likely:

```
{
  "tasks": ["classification", "summarization", "tool_use"],
  "methods": ["tgd", "momentum", "evo", "opro", "ape", "sweep"],
  "results": [
    {"task": "classification", "method": "tgd", "seed": 0,
     "score": 0.82, "tokens": 12345, "latency_ms": 567}
  ],
  "metadata": {...}
}
```

If the actual shape differs, match what the script produces — don't
force the script to change.

### Page IA

```
/benchmarks           — list of stored reports + leaderboard
/benchmarks/:id       — single report detail
```

**Detail page**:

```
┌─────────────────────────────────────────────────────┐
│ Benchmark report — created 2026-04-25  [tag] [del] │
├─────────────────────────────────────────────────────┤
│  Method × Task matrix                               │
│           classification  summarization  tool_use   │
│  tgd        0.82±0.03      0.71±0.05    0.65±0.04   │
│  momentum   0.84±0.02      0.74±0.04    0.68±0.03   │
│  evo        0.79±0.05      0.73±0.06    0.62±0.07   │
│  ...                                                │
├─────────────────────────────────────────────────────┤
│  Cost-vs-metric scatter (all task×method×seed dots) │
├─────────────────────────────────────────────────────┤
│  Per-task leaderboards (best method per task)       │
└─────────────────────────────────────────────────────┘
```

### "Freeze and tag" workflow

A "tag" is a named version. `POST /benchmarks/{id}/tag {tag: "v1"}`
records it. Subsequent reports can show ∆ vs the latest tagged
baseline (simple table next to the matrix: "+0.03" / "-0.01" per cell).

### Persistence

Default: in-memory store, lives in the dashboard process. Reports
disappear on restart. If 4-4 lands first, use the SQLite store.

For local dev, also support reading reports from a configured
directory: `--benchmark-dir ./.benchmarks/` so `make demo`-style
workflows can work without curl.

## Acceptance criteria

1. Run `uv run python examples/benchmark/run.py --offline --out
   /tmp/report.json` (or whatever the script's flags are; investigate).
2. `curl -X POST http://localhost:7860/benchmarks/_ingest -d @/tmp/report.json`
   returns `{id: "..."}`.
3. Visit `/benchmarks/{id}` → see the matrix, scatter, and per-task
   leaderboards.
4. Tag the report → see the tag in the list page.
5. Delete the report → it's gone from the list.
6. Tests for: schema validation, tag idempotency, matrix rendering,
   scatter dimensionality.

## Dependencies & contracts

### Depends on

- 4-4 (optional): if SQLite-backed store is desired. Otherwise
  in-memory is fine.
- `examples/benchmark/run.py` produces the JSON shape this consumer
  expects. **Investigate** the script before assuming. If the shape is
  unfriendly, the smaller fix is on the consumer side; don't change
  the script unless the case is overwhelming.

### Exposes

- `/benchmarks/*` API.
- `<BenchmarkMatrix />` and `<MethodLeaderboard />` components.

## Direction notes / SOTA hints

- For matrix rendering with mean±stddev cells, a simple HTML table is
  fine. Heatmap-style coloring optional but tasteful.
- For the leaderboard, a sortable table with a "best in green" tint
  works. Don't over-style.
- Cost-vs-metric scatter: same as 4-1's component (consider importing
  if conflict-free; otherwise duplicate — minor code, not worth a
  cross-task dependency).

## Risks / non-goals

- Don't add a "rerun benchmark" button that triggers
  `examples/benchmark/run.py` — that's a different surface.
- Don't add benchmark scheduling.
- Don't compare different schemas (versioned schema; reject incompatible).

## Verification checklist

- [ ] Real bench script output ingests cleanly.
- [ ] Matrix and scatter render correctly.
- [ ] Tag survives across page reload (in-memory persists for the
      dashboard's lifetime).
- [ ] Tests pass.
