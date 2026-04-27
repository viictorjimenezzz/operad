# 05 — Algorithm: Sweep

**Stage:** 3 (parallel; depends on Briefs 01, 02, 14, 15)
**Branch:** `dashboard-redesign/05-algo-sweep`
**Subagent group:** B (Algos-quant)

## Goal

Make the Sweep view actually about sweeps. Today the layout exists but
nothing renders it because Brief 02 is the wire-up. With routing
landed, the Sweep page reads `sweep.json` and renders an algorithm-
specific tab set. This brief writes the tab bodies: a heatmap with a
**dimension picker** (Q1 answer), a `RunTable` of cells, a cost
totalizer, and a best-cell card.

The dimension picker is the most important new behavior: when the
sweep covers ≥3 axes, the user picks two to display and aggregates the
rest.

## Read first

- Sweep emits per-cell events; data shape is in
  `apps/dashboard/operad_dashboard/routes/sweep.py:91-98` and emit
  sites at `operad/algorithms/sweep.py:140-156`. Each `cell` event
  carries `{cell_index, parameters: dict[str, Any], score: None|float}`.
- `RunInfo` aggregates them via `runs.py:141-152` (`_record_algo` →
  `cells`). The route returns `{cells, axes, score_range, best_cell_index, total_cells, finished}`.
- `apps/frontend/src/components/charts/sweep-heatmap.tsx` — current
  auto-mode chart (1D bar / 2D matrix / 3D small multiples). Read it
  closely; we extend it.
- `apps/frontend/src/components/charts/sweep-best-cell-card.tsx` and
  `sweep-cost-totalizer.tsx` — useful as Overview content.
- `apps/frontend/src/layouts/sweep.json` — the existing layout (Brief
  02 added universal tabs; this brief fleshes the per-algo tabs).
- `INVENTORY.md` §7 (Sweep description), §9 (BenchmarkSuite — Sweep is
  often used inside benchmark grids).

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/sweep/sweep-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/sweep/sweep-heatmap-tab.tsx`
- `apps/frontend/src/components/algorithms/sweep/sweep-cells-tab.tsx`
- `apps/frontend/src/components/algorithms/sweep/sweep-dimension-picker.tsx`
  (per `00-CONTRACTS.md` §2.6)
- `apps/frontend/src/components/algorithms/sweep/parallel-coordinates.tsx`
  (a thin SVG parallel-coords plot; falls back to "use heatmap" when
  axes ≤ 2)

Edit:

- `apps/frontend/src/layouts/sweep.json` — fill the per-algo tabs with
  the new components (the universal `Agents` / `Events` / `Graph` tabs
  are already in place from Brief 02).
- `apps/frontend/src/components/algorithms/sweep/registry.tsx` — register
  the new components for the JSON renderer.
- `apps/frontend/src/components/charts/sweep-heatmap.tsx` — extend to
  accept controlled `[xAxis, yAxis]` props and `aggregations` props,
  computing aggregate per cell when more than the displayed axes exist.
- Fix the `value: 0` bug in `sweep.json`'s events KPI tile
  (proposal.md §6.5 mentions this is hard-coded).

## Tab structure (final)

Per `00-CONTRACTS.md` §1, the tabs are:

```
[ Overview ] [ Heatmap ] [ Cells ] [ Cost ] [ Agents ] [ Events ] [ Graph ]
```

`Agents`, `Events`, `Graph` are universal (Brief 02 + 15). The four
sweep-specific tabs are the body of this brief.

### Overview

```
─── KPI strip ────────────────────────────────────────
[ axes: 3 ] [ cells: 27 ] [ ok: 26 ] [ failed: 1 ]
[ best score: 0.91 ] [ cost: $0.41 ] [ runtime: 3m 22s ]

─── best cell card (existing SweepBestCellCard) ─────
Best: temperature=0.4, top_p=0.9, model=gpt-4o
Score: 0.91   Cost: $0.014   Latency: 1.2s

─── cost totalizer (existing SweepCostTotalizer) ───
Cells completed: 26 / 27    Cumulative cost: $0.41
[ scatter: cell index × score ]
```

This is mostly composing existing components. Replace the `value: 0`
hardcoded events tile with `$queries.summary.event_total`.

### Heatmap

The interesting tab. Contents:

```
─── dimension picker ────────────────────────────────
X axis: [ temperature ▾ ]   Y axis: [ top_p ▾ ]
Aggregate over:
  model: [ mean ▾ ]   renderer: [ mean ▾ ]

─── heatmap (auto-pick by axis count) ──────────────
1 axis           → bar chart (one bar per value, height = score)
2 axes (default) → matrix (rows × cols, color = score)
3+ axes          → matrix of selected pair, aggregating others
                   per the picker. A "view as parallel coordinates"
                   toggle switches to the parallel-coords plot.

─── tooltip on hover ───────────────────────────────
{ temperature: 0.4, top_p: 0.9 }
score: 0.87 (mean of 3 cells: model=gpt-4o, gpt-4o-mini, claude-3.5)
cost: $0.014   latency: 1.2s
[ Open: cell #14 → /agents/<hash>/runs/<runId> ]
```

Click a cell:
- For 1-2 axes: jumps to the synthetic-child run for that combination.
- For 3+ axes (where the cell is an aggregate): opens a popover listing
  the underlying cells with scores, each linkable to its synthetic
  child.

### Cells

A `RunTable` of every cell. Columns:

```
[●][State][Cell #][<axis 1>][<axis 2>]…[<axis N>][Score][Cost][Latency][Run]
```

Axis columns are dynamically generated from `sweep.axes`. Storage key
`sweep-cells:<runId>`. Click a row → `/agents/:hash/runs/:cellRunId`
(the synthetic child).

The "Run" column is a deep-link icon.

### Cost

```
─── cost vs score scatter ──────────────────────────
x: cumulative cost    y: best-score-so-far
(one point per cell, time-ordered)

─── cost by axis ───────────────────────────────────
For each swept axis, a stacked-bar of cost contribution per value.

─── pareto frontier ────────────────────────────────
Cells on the {cost, score} pareto frontier. A toggle "minimize/maximize
score" depending on metric direction.
```

`SweepCostTotalizer` already does the first chart; this tab adds the
two new visualizations as panels in a `PanelGrid`.

## Dimension picker semantics (Q1)

Per `00-CONTRACTS.md` §2.6.

- `axes.length === 1` → picker is hidden; bar chart only.
- `axes.length === 2` → picker is hidden; matrix.
- `axes.length >= 3` → picker shown above the heatmap.
  - X-axis dropdown lists all axes.
  - Y-axis dropdown lists all axes (and "(none)" for 1-D mode).
  - Below: one row per *unselected* axis with an aggregation dropdown
    `{mean, min, max, median, count}`.
- The picker's state syncs to the URL (`?dim=axisX,axisY` plus
  `?agg=axis:fn,...` for the rest).
- Defaults: x = first numeric axis, y = second numeric axis,
  aggregations all `mean` for numeric and `count` for non-numeric.

When `score` is null for every cell (Sweep doesn't natively score —
proposal §3.2 of the data report), every cell is "unscored". Render the
heatmap with cell *colors based on completion state* (green = ok, red =
failed, gray = pending) and the value labels showing... nothing. Add an
`EmptyState` overlay with the message: "this sweep didn't define a
score function — see /agents/:hash/runs/:cellRunId for individual
results". This is correct for plain `Sweep` runs that don't subclass to
emit a score.

## Universal Agents tab override

The universal `Agents` tab (Brief 15) defaults to grouping synthetic
children by inner-agent `hash_content`. For Sweep, this collapses 27
cells into "1 group of 27 Reasoner runs" — useful but obscures the
per-cell parameter variation. Add a Sweep-specific tab override:

```json
"agents": {
  "type": "AgentsTab",
  "props": {
    "runId": "$context.runId",
    "groupBy": "none",
    "extraColumns": ["score", "axisValues"]
  }
}
```

`AgentsTab` (Brief 15) already supports a `groupBy` prop with values
`"hash" | "none"`. Sweep overrides to `"none"` and adds two columns
showing the cell's score and concise axis values
(`temperature=0.4, top_p=0.9`).

## Design alternatives

### A1: Heatmap dimension picker UI

- **(a)** Two dropdowns + per-axis aggregation row (recommended).
  Standard W&B sweep parallel-coords style.
- **(b)** Drag-to-rearrange axes header. **Reject:** fancy and
  overkill; the dropdown matches the proposal.

### A2: How to handle 4+ axes

- **(a)** Aggregate over unselected axes (recommended).
- **(b)** Slice — pick a single value from each unselected axis (a
  cube slicer). **Reject:** inferior to aggregation when scores are
  noisy.
- **(c)** Force user to drop to parallel coordinates. Possibly include
  this as a "try parallel coords" affordance for 4+ axes alongside
  (a).

### A3: Score-less sweeps

- **(a)** Color cells by completion state, overlay empty-state message
  (recommended).
- **(b)** Hide the heatmap tab entirely. **Reject:** loses the cost-by-
  axis insights.

## Acceptance criteria

- [ ] `/algorithms/:runId` for a Sweep run shows tabs:
  `Overview · Heatmap · Cells · Cost · Agents · Events · Graph`.
- [ ] Overview shows axes count, cells count, ok/failed split, best
  score, total cost, runtime KPIs; the existing best-cell card; the
  existing cost totalizer scatter.
- [ ] Heatmap auto-picks 1D / 2D mode; 3+ axes shows a working dimension
  picker; URL state syncs.
- [ ] Hovering a cell shows a tooltip with the parameters and score (or
  aggregate) and a link to the underlying synthetic child run.
- [ ] Score-less sweeps show the cells-by-completion view + empty
  message instead of an unintelligible heatmap.
- [ ] Cells tab has a `RunTable` with one row per cell and one column
  per axis; clicking opens the synthetic child.
- [ ] Cost tab shows pareto frontier and per-axis cost breakdown.
- [ ] Agents tab is overridden to `groupBy: "none"` and adds score +
  axisValues columns.
- [ ] The previously hard-coded `value: 0` events KPI is bound to
  `summary.event_total`.
- [ ] `pnpm test --run` green; `make build-frontend` green.
- [ ] Manual smoke against an example sweep (any `examples/benchmark/`
  invocation).

## Test plan

- **Unit:** `sweep-dimension-picker.test.tsx` covers the 1D/2D/3D
  branches and the URL state sync; `parallel-coordinates.test.tsx`
  covers the SVG fallback; `sweep-cells-tab.test.tsx` covers the
  dynamic axis columns.
- **Snapshot:** `sweep.json` against the Tabs schema.
- **Visual:** screenshots of all four tabs against an `examples/benchmark`
  Sweep run.

## Out of scope

- Wiring the route (Brief 02).
- Universal Agents/Events/Graph tabs (Brief 15).
- Backend changes to Sweep payload (the Sweep payload is already rich
  enough; no backend delta required).

## Hand-off

PR body must include:
1. Acceptance-criteria checklist with file:line evidence.
2. Three screenshots: heatmap-2D, heatmap-3D-with-picker, cells table.
3. The heatmap response time on a 222-cell synthetic sweep
   (performance smoke test — should render under 200ms).
