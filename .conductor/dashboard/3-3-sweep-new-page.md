# 3-3 — Sweep page (new)

> **Iteration**: 3 of 4. **Parallel slot**: 3.
> **Owns**: a NEW Sweep layout, NEW heatmap component, NEW backend
> route file.
> **Forbidden**: other layouts/components/routes.

## Problem

`Sweep` is operad's grid-search algorithm — Cartesian product over
parameter cells, each cell evaluated. It produces a `SweepReport` with
all cells × scores. Today there is **no** Sweep layout in
`apps/frontend/src/layouts/`, so Sweep runs fall through to
`default.json` which doesn't visualize the parameter grid.

A 2-d sweep over (temperature, max_tokens) with 5×5 = 25 cells should
render as a 5×5 heatmap colored by score, with axis labels for the
parameter values, and per-cell click → drill into that cell's run.

## Scope

### Owned files

- New: `apps/frontend/src/layouts/sweep.json`
- New: `apps/frontend/src/shared/charts/sweep-heatmap.tsx` — N-d
  parameter heatmap (1d → bars, 2d → matrix, ≥3d → small-multiples or
  a parallel-coordinates fallback).
- New: `apps/frontend/src/shared/charts/sweep-best-cell-card.tsx` — a
  KPI card highlighting the best cell.
- New: `apps/frontend/src/shared/charts/sweep-cost-totalizer.tsx` —
  total tokens / cost / time across all cells.
- New: `apps/dashboard/operad_dashboard/routes/sweep.py` — aggregation
  endpoint.
- Tests.

### Forbidden files

- Other layouts, other algorithm components.
- Generic infra.

## Direction

### Investigate the runtime

Read `operad/algorithms/sweep.py`. Sweep emits a per-cell event;
verify the payload shape. Likely:

```
algo_event kind="cell" payload:
  { "cell_index": int,
    "parameters": {name: value, ...},
    "score": float,
    "tokens": int,
    "latency_ms": float }

algo_event kind="algo_end" payload:
  { "best_cell_index": int,
    "best_score": float,
    "total_cells": int }
```

### Backend: `routes/sweep.py`

- `GET /runs/{id}/sweep.json` → `{cells: [...], best_cell, axes:
  [{name, values}], score_range: [min, max]}`.
- `GET /runs/{id}/sweep.sse` for live updates as cells complete.

The "axes" field is computed by collecting unique values per
parameter name across all cells. Useful for axis-labeling the heatmap.

### `<SweepHeatmap />`

Render based on dimensionality:

- **1-d** (one parameter swept): horizontal bar chart, one bar per
  value, colored by score.
- **2-d**: matrix grid (rows = axis-1 values, cols = axis-2 values),
  cells colored by score (use a sequential colormap; shadcn has CSS
  variables you can interpolate, or use d3-scale-chromatic).
- **3-d+**: small-multiples (one 2-d heatmap per third-axis value),
  or a parallel-coordinates plot via the `recharts` `LineChart`. Pick
  whichever is simpler.

Cell click → navigate to that cell's child run (which has its own
run_id since it's a synthetic sub-run; use the parent_run_id linkage
from 1-2).

### Best-cell card

Top-of-page KPI:

- Parameter values for best cell.
- Score with confidence interval if available.
- Cost incurred to find the best (sum of all cell costs).

### Cost totalizer

A small panel summing tokens / latency / wall time across all cells,
plus per-cell cost-vs-score scatter as a "cost-of-search" indicator.

### Layout

```
sweep.json tabs:
  - Overview: best-cell card + cost totalizer
  - Heatmap: full sweep heatmap
  - Cells: tabular list of all cells (sortable by score, params)
  - Graph
  - Events
```

## Acceptance criteria

1. Run a Sweep demo (compose if no demo exists; the offline test
   suite likely has one in `tests/algorithms/`). Navigate to the run
   → heatmap renders correctly with axis labels.
2. Best-cell card highlights the right cell.
3. Click on a cell navigates to its child run page.
4. 1-d sweep degrades to bar chart; 2-d shows matrix; 3-d shows
   small multiples without crashing.
5. Tests for the route, heatmap rendering, and dimensionality
   detection.

## Dependencies & contracts

### Depends on

- 1-1, 1-2 (synthetic-run linkage so cells link back to parent),
  2-2 (renderer auto-discovery), 3-5 (Langfuse card).

### Exposes

- `/runs/{id}/sweep.json|.sse`.
- `<SweepHeatmap />` reusable as a primitive.

## Direction notes / SOTA hints

- Color scales: `d3-scale-chromatic` is small and battle-tested. Or
  hand-roll using HSL interpolation; ~10 lines.
- For the matrix layout, a simple CSS grid with `grid-template-columns:
  repeat(N, 1fr)` works. No need for SVG unless you want axis ticks.
- Recharts has `<ScatterChart />` for cost-vs-score; trivially fits.

## Risks / non-goals

- Don't try to handle >5-dimensional sweeps elegantly — print a
  "view as table" fallback and call it done.
- Don't add re-run controls or "narrow the sweep" interactions.
- Don't compute statistical significance across cells.

## Verification checklist

- [ ] Synthetic 2-d sweep renders correctly.
- [ ] Click-to-drill navigation works.
- [ ] Backend route tests pass.
- [ ] Frontend tests pass.
