# 05-01 Sweep — heatmap, cells, parallel-coordinates

**Branch**: `dashboard/algo-sweep`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02` (RunTable cell kinds), `02-05` (KPIs),
`04-01` (ParametersTab — Sweep does not mutate, so no Parameters tab
here)
**Estimated scope**: medium

## Goal

Replace `apps/frontend/src/layouts/sweep.json` with a Sweep-shaped
view: `Overview · Heatmap · Cells · Parallel coords · Cost · Agents
· Events`. The bespoke addition is **parallel coordinates** — the
W&B sweep landmark — implemented as a new `SweepParallelCoordsTab`
component.

## Why this exists

- §11 of `00-contracts.md` reserves `SweepParallelCoordsTab`.
- Sweeps are inherently multi-axis; the heatmap collapses to 2D, the
  parallel-coords view shows N-D in one chart.

## Files to touch

- `apps/frontend/src/layouts/sweep.json` — replace the spec.
- New: `apps/frontend/src/components/algorithms/sweep/parallel-coords-tab.tsx`.
- New: `apps/frontend/src/components/algorithms/sweep/parallel-coords-tab.test.tsx`.
- `apps/frontend/src/components/algorithms/registry.tsx` — register
  the new tab.

## Contract reference

`00-contracts.md` §3 (palette), §5 (RunTable), §11 (element types),
§12 (KPIs).

## Implementation steps

### Step 1 — Update layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "overview", "label": "Overview" },
      { "id": "heatmap", "label": "Heatmap" },
      { "id": "cells", "label": "Cells" },
      { "id": "parallel", "label": "Parallel coords" },
      { "id": "cost", "label": "Cost" },
      { "id": "agents", "label": "Agents", "badge": "$expr:count($queries.children)" },
      { "id": "events", "label": "Events", "badge": "$queries.summary.event_total" }
    ]
  },
  "children": ["overview","heatmap","cells","parallel","cost","agents","events"]
},
```

Drop the `graph` tab — graph is a per-cell concern.

### Step 2 — `SweepParallelCoordsTab`

Axes = the sweep's parameter dotted paths (read from `sweep.json`
data — the sweep summary already exposes `axes`). Each polyline =
one cell. Color = score (heatmap-like gradient via
`--qual-N` or a sequential ramp). Hover a polyline → highlight + show
all axis values; click → navigate to the child run.

Simple SVG implementation; do not introduce a new charting dep. Use
the same techniques as `population-scatter.tsx` for axis ticks.

### Step 3 — Cells tab uses new RunTable cell kinds

Convert `SweepCellsTab` (existing) to use `kind: "param"` for axis
columns and `kind: "score"` for the score column. The horizontal
mini-bars and value-vs-previous indicators are immediate wins.

## Design alternatives

1. **Render parallel coords with `d3` vs hand-rolled SVG.**
   Recommendation: hand-rolled. The chart is simple; the dependency
   cost is high.
2. **Color-by-score vs color-by-cell-id.** Recommendation: by score.
   Sweeps are explicitly score-driven; identity coloring of cells
   is meaningless to the user.

## Acceptance criteria

- [ ] `Sweep` runs render the new tab strip.
- [ ] Parallel coords renders one polyline per cell with correct axis
  values; hover highlights; click navigates.
- [ ] Cells tab uses `param` and `score` cell kinds.
- [ ] `pnpm test --run` passes; layout JSON parse passes.

## Test plan

- `parallel-coords-tab.test.tsx`: 3-axis fixture × 6 cells; assert 6
  polylines render.
- Visual: example 02 (Sweep) renders all tabs.

## Stretch goals

- Brushing on parallel-coords axes filters polylines (W&B does
  this).
- Reordering axes by drag-and-drop persists in URL.
- A small "show top-N" cell highlight that dims other polylines.
