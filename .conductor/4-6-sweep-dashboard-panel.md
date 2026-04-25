# `Sweep` dashboard integration: parallel-coordinates panel

## Goal
`Sweep` already returns `SweepReport` / `SweepCell`; the dashboard already has a fitness panel. Pipe sweep cells into a parallel-coordinates view so users can see the parameter × score landscape at a glance. Sweep is one of the most operationally-useful algorithms — making it visible boosts the library's "you can see what's happening" promise.

## Context
- `operad/algorithms/sweep.py` — emits cell results.
- `apps/dashboard/operad_dashboard/routes/` — `fitness.py`, `mutations.py`, `drift.py`, etc.
- Parallel-coordinates plot: standard d3/observable visualization; axis per parameter, polyline per cell, color-by-score.

## Scope

**In scope:**
- `operad/algorithms/sweep.py` — confirm it emits an `AgentEvent` per cell with `{cell_id, params: dict, score: float, metrics: dict}` shape; if it doesn't, add the emission. Keep the existing `SweepReport` return-shape unchanged.
- `apps/dashboard/operad_dashboard/routes/sweep.py` (new) — `GET /runs/{run_id}/sweep.json` returning the cells.
- `apps/dashboard/operad_dashboard/templates/run_detail.html` — add the panel (only when sweep events present).
- `apps/dashboard/operad_dashboard/static/sweep.js` — parallel-coordinates rendering. Use a small embeddable lib or hand-rolled SVG; avoid heavy deps.
- `apps/dashboard/tests/test_sweep_panel.py` — contract test (route returns expected shape, panel renders when data present, omits when absent).
- INVENTORY §13 — add the panel row.

**Out of scope:**
- Changing `Sweep`'s search space or scoring.
- Adding new chart types.
- Anything outside `operad/algorithms/sweep.py` and `apps/dashboard/`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/demos/agent_evolution/`, `Makefile`, `scripts/`, `examples/benchmark/`, `tests/runtime/test_otel_langfuse.py`, `apps/dashboard/operad_dashboard/contracts.py` (4-2 owns; coordinate by adding the new sweep contract row in your PR if 4-2 has merged).

## Implementation hints
- Cell event payload: keep `params` as a flat dict (`{"reasoner.role": "...", "reasoner.temperature": 0.5}`) so the parallel-coordinates JS can build axes mechanically.
- The panel should hide axes that are constant across all cells (no signal).
- If `score` is a dict (multi-metric), pick a primary key from the algorithm's metric config; users can swap it via a panel selector.
- For rendering, plain `<svg>` with d3-style polylines is enough; avoid React or a charting framework. Match the existing dashboard's static-asset story.

## Acceptance
- Sweep cells visible on the run-detail page when a sweep run is active.
- Panel hidden cleanly when no sweep events.
- Contract test pins the JSON shape.
- INVENTORY updated.
