# 00 — Shared contracts

This document is the single source of truth for any type, prop, route, or
constant that crosses brief boundaries. If your brief and this document
disagree, this document wins. If something you need is not here, **stop
and ask** — do not freelance shared types.

Anchor for cross-brief vocabulary:

- **Run** = one `OperadOutput.run_id` (`operad/core/agent.py` envelopes).
- **Invocation** = one root-agent end-event under a Run. A Run *can* have
multiple invocations when the same agent is called multiple times in
the same process (e.g., multi-turn).
- **Group** = the set of Runs that share `hash_content`. The Agents rail
is grouped by Group.
- **Synthetic child** = a Run whose first envelope carried
`metadata.parent_run_id` (set by `Agent._invoke_envelope` when an
algorithm wraps the call in `_enter_algorithm_run`). Algorithm-spawned
agent invocations are synthetic children.
- **Algorithm** = a Run with `is_algorithm = True` and a non-null
`algorithm_path`. Always emits at least `algo_start` and `algo_end`.

## 1. JSON layout schema (extension)

The existing schema in `apps/frontend/src/lib/layout-schema.ts` stays.
Two conventions become mandatory across all per-class layouts:

- **Root element is `Tabs`.** No exceptions. The root element type is
`"Tabs"`, its `props.tabs` is an array of `{ id, label, badge? }`,
and its `children` is an array of element ids that match
`props.tabs[i].id` 1:1.
- **Universal tabs.** Every per-algorithm/training/agent layout
declares the universal tabs `Agents` and `Events` *last*, in that
order. Per-class tabs go in between. The single exception is the
Trainer rail, which adds an extra `Traceback` tab when present
(Brief 13).
- **Algorithm-specific tabs come first**, before `Agents` and `Events`.
Order: `Overview` → algorithm tabs → `Agents` → `Events` → `Graph`.

Example (canonical Beam shape):

```json
{
  "type": "Tabs",
  "props": {
    "tabs": [
      {"id": "overview",   "label": "Overview"},
      {"id": "candidates", "label": "Candidates"},
      {"id": "agents",     "label": "Agents",  "badge": "$queries.children.length"},
      {"id": "events",     "label": "Events",  "badge": "$queries.summary.event_total"},
      {"id": "graph",      "label": "Graph"}
    ]
  },
  "children": ["overview","candidates","agents","events","graph"]
}
```

Brief 02 adds `Tabs` as a first-class element type to the renderer; today
it's hidden behind a generic `Stack` fallback.

## 2. Component registry — new + redesigned primitives

The following components are introduced or redefined as part of this
redesign. Their props are part of the cross-brief contract.

### 2.1 `RunTable` (Brief 01)

Path: `apps/frontend/src/components/ui/run-table.tsx`. The replacement
for every hand-rolled run list across the dashboard.

```ts
type RunRow = {
  id: string;                          // run_id, invocation id, or cell id
  identity: string;                    // hash_content (groups) or run_id (rows)
  state: "running" | "ended" | "error" | "queued";
  startedAt: number | null;
  endedAt: number | null;
  durationMs: number | null;
  // Open-ended structured columns:
  fields: Record<string, RunFieldValue>;
};

type RunFieldValue =
  | { kind: "text"; value: string; mono?: boolean }
  | { kind: "num"; value: number | null; format?: "tokens" | "cost" | "ms" | "score" | "int" | "float" }
  | { kind: "pill"; value: string; tone: "ok" | "warn" | "error" | "live" | "accent" | "default" }
  | { kind: "hash"; value: string }
  | { kind: "sparkline"; values: (number | null)[] }
  | { kind: "link"; label: string; to: string }
  | { kind: "markdown"; value: string };

type RunTableColumn = {
  id: string;
  label: string;
  // dotted path into RunRow.fields, or a special key:
  //   "_id" | "_state" | "_started" | "_ended" | "_duration" | "_color"
  source: string;
  align?: "left" | "right";
  sortable?: boolean;
  defaultSort?: "asc" | "desc";
  width?: number | "1fr";
  defaultVisible?: boolean;
  /** When true, renders the per-row hashColor as a 4-px left rail. */
  isColorRail?: boolean;
};

interface RunTableProps {
  rows: RunRow[];
  columns: RunTableColumn[];
  /** Stable key for column-visibility persistence in localStorage. */
  storageKey: string;
  /** Click row → navigate to this URL builder; if absent, no navigation. */
  rowHref?: (row: RunRow) => string | null;
  /** Multi-select for compare. Brief 03 surfaces compare via /experiments. */
  selectable?: boolean;
  onSelectionChange?: (selected: string[]) => void;
  /** Empty-state title + description. */
  emptyTitle?: string;
  emptyDescription?: string;
  /** Pagination. */
  pageSize?: number;            // default 50
  /** Optional grouping; when set, rows render under collapsible group headers. */
  groupBy?: (row: RunRow) => { key: string; label: string };
  /** Density. */
  density?: "compact" | "cozy"; // default "compact"
}
```

Required behaviors:

- **Color rail.** First column is always a 4-px-wide rail. Color comes
from `hashColor(row.identity)` (see §3). When the row is the active
one (matched by route), the rail thickens to 6px.
- **Sortable headers.** Click toggles asc/desc; URL state syncs to
`?sort=col,dir` so a refresh restores ordering.
- **Column visibility.** A "Columns" menu in the header toggles
visibility, persisted under `localStorage[storageKey]`.
- **Sparkline column.** Renders inline using `Sparkline` (existing
primitive) at 60×16 px, colored by `hashColor(row.identity)`.
- **Pager** at the footer when `rows.length > pageSize`.

The old `RunsTable` literals in `AgentGroupPage.tsx`,
`AgentGroupSubpages.tsx`, `AlgorithmsIndexPage.tsx`,
`TrainingIndexPage.tsx`, and `AgentsIndexPage.tsx` are deleted (Brief 04

- index pages).

### 2.2 `MetricSeriesChart` (Brief 04)

A wrapper around the (bug-fixed) `MultiSeriesChart` that takes a
**single multi-point series** plus an optional **delta-vs-group**
overlay.

```ts
interface MetricSeriesChartProps {
  /** Ordered points (x = invocation index or wall time, y = metric). */
  points: { x: number; y: number | null; runId: string }[];
  identity: string;             // group hash_content (drives series color)
  height?: number;              // default 200
  formatY?: (n: number) => string;
  formatX?: (n: number) => string;
  /** Optional dashed reference line (group p50 / threshold / etc). */
  reference?: { y: number; label: string };
  /** Highlight one point — used by single-invocation Metrics tab to
   *  show "you are here" relative to the group series. */
  highlightX?: number;
}
```

This replaces the per-run-1-point degenerate series across both the
group page and the agent group cost tab. See Brief 04 for the data
shape and Brief 03 for the single-invocation usage.

### 2.3 `CollapsibleSection` (Brief 03)

A flat panel with an inline preview + chevron-driven expansion, used to
replace the four-card "Definition" grid on the single-invocation
Overview.

```ts
interface CollapsibleSectionProps {
  id: string;                     // for URL #fragment to deep-link an open section
  label: string;                  // "Identity", "Backend", "Examples"
  /** One-line preview rendered next to the chevron when collapsed. */
  preview: ReactNode;
  /** Default-collapsed unless the URL hash matches `id`. */
  defaultOpen?: boolean;
  children: ReactNode;
}
```

Implementation note: the existing `Section` primitive
(`apps/frontend/src/components/ui/section.tsx`) is *almost* this shape
but its preview/expanded API does not match. Either extend `Section` or
add `CollapsibleSection` as a sibling — Brief 03 chooses.

### 2.4 `MarkdownView` and `MarkdownEditor` (Brief 14)

For run notes (Markdown per Q5) and any user-authored text we render.

```ts
interface MarkdownViewProps {
  value: string;
  /** When omitted, no edit affordance. */
  onSave?: (next: string) => Promise<void>;
}
```

The view shows rendered Markdown. When `onSave` is provided, a small
"edit" pencil is shown; clicking opens an inline textarea with
preview/save/cancel.

Use a small dependency: `react-markdown` is already in the bundle
implicitly via existing chart components — verify via
`pnpm why react-markdown` before adding; if absent, add it.

### 2.5 `ScenarioTreeView` (Brief 09)

Used by the TalkerReasoner Tree tab. Q6 answer = interactive.

```ts
interface ScenarioTreeViewProps {
  /** From algo_start.payload (extended in Brief 14). */
  tree: {
    nodes: { id: string; title: string; prompt: string; terminal: boolean; parent_id: string | null }[];
    name: string;
    purpose: string;
    rootId: string;
  };
  /** Path of node ids walked, in order. */
  walkedPath: string[];
  /** Current node id (the run pulses on this node). */
  currentNodeId: string | null;
  /** Click handler — selects a node, parent shows turns spent there. */
  onNodeSelect?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}
```

Implementation uses `@xyflow/react` (already a dependency for
`AgentFlowGraph`). The layout is hierarchical (top-down) using `dagre`.

### 2.6 `SweepDimensionPicker` (Brief 05)

Sweep tables (Q1 answer): for ≤2 axes auto-pick (1D bar, 2D matrix); for
≥3 axes, the user picks 2 axes and the rest collapse via aggregation.

```ts
interface SweepDimensionPickerProps {
  axes: { name: string; values: (string | number | boolean | null)[] }[];
  selected: [string, string | null];   // [x_axis, y_axis | null for 1D]
  onChange: (next: [string, string | null]) => void;
  /** When 3+ axes are present, an "aggregate over" multi-select is shown
   *  for each unselected axis (mean | min | max | median | count). */
  aggregations: Record<string, "mean" | "min" | "max" | "median" | "count">;
  onAggregationsChange: (next: Record<string, "mean" | "min" | "max" | "median" | "count">) => void;
}
```

When 1 axis: render a `Bar` (1D `SweepHeatmap` mode). When 2 axes:
render the matrix mode. When 3+ axes and the user selects 2: aggregate
the remaining axes per the picker, render the matrix.

## 3. Color palette

**Q4 answer: curated palette, no backwards compatibility.**

### 3.1 Tokens

In `apps/frontend/src/styles/tokens.css`:

```css
:root, .dark {
  /* Curated 12-hue qualitative palette, vivid on dark, legible on light. */
  --qual-1:  hsl(  4, 78%, 60%);  /* coral */
  --qual-2:  hsl( 28, 90%, 58%);  /* tangerine */
  --qual-3:  hsl( 50, 88%, 56%);  /* gold */
  --qual-4:  hsl( 90, 60%, 50%);  /* lime */
  --qual-5:  hsl(140, 55%, 48%);  /* fern */
  --qual-6:  hsl(170, 60%, 45%);  /* teal */
  --qual-7:  hsl(196, 78%, 56%);  /* sky (matches existing accent) */
  --qual-8:  hsl(220, 70%, 62%);  /* indigo */
  --qual-9:  hsl(255, 65%, 65%);  /* lavender */
  --qual-10: hsl(290, 60%, 60%);  /* magenta */
  --qual-11: hsl(330, 70%, 60%);  /* pink */
  --qual-12: hsl(355, 30%, 50%);  /* rose-gray */
}
```

### 3.2 `hashColor` rounds to the palette

`apps/frontend/src/lib/hash-color.ts` is rewritten to:

1. Hash the input identity to a stable integer (existing `hashCode`).
2. Modulo 12 to pick `i ∈ [0,11]`.
3. Return `var(--qual-${i+1})`.

Old `hsl(...)` outputs are gone. **No** consumers compute their own hue.

### 3.3 Where colors live in the UI

- Sidebar dot for a Group: `hashColor(group.hash_content)`.
- Sidebar dot for a Run row inside a Group: `hashColor(run.run_id)` (so
individual invocations differ inside their group).
- Chart series colored by `hashColor(seriesIdentity)`. Brief 04 supplies
the convention per chart.
- `RunTable` left-rail: `hashColor(row.identity)` — see §2.1.
- `HashTag` (`apps/frontend/src/components/ui/hash-tag.tsx`) reads
`hashColor` for both `dotOnly` and full mode.
- The accent color (`--color-accent`) remains independent and is used for
interactive primary actions (links, tabs, focus rings). It is NOT a
hash color.

### 3.4 State colors are unchanged

`--color-ok`, `--color-warn`, `--color-err`, `--color-live` remain as
existing semantic colors and are not part of the qual palette.

## 4. Backend route contracts

### 4.1 New endpoints (Brief 14)

```
GET  /api/agents/:hash/metrics
     ?metric=<name>               # optional; default = all
     ?range=<runId>:<runId>       # optional; default = all
  →  {
       hash_content: str,
       metrics: {
         <metric_name>: {
           unit: str | null,         # "ms" | "tokens" | "usd" | null
           series: [
             {run_id: str, started_at: float, value: number | null}
           ]
         }
       }
     }
```

Built-in metrics: `latency_ms`, `prompt_tokens`, `completion_tokens`,
`cost_usd`. Plus any user-defined metric collected via the `metrics` field
on `OperadOutput.metadata` (§5).

```
GET  /api/agents/:hash/parameters
  →  {
       hash_content: str,
       paths: [str, ...],          # all trainable parameter paths seen
       series: [
         {
           run_id: str,
           started_at: float,
           values: { <path>: { value: <serialized>, hash: str } }
         }
       ]
     }
```

Each parameter's `hash` is `hashlib.sha256(repr(value)).hexdigest()[:16]`.
Used for the parameter-evolution lane (Brief 04 Train tab).

```
PATCH /api/runs/:id/notes
      Body: {"markdown": str}
  →   {"run_id": str, "notes_markdown": str, "updated_at": float}
```

Notes persist in the SQLite archive store (existing `persistence.py`).
The `notes_markdown` field is added to `RunSummary` (default `""`).

### 4.2 Enhanced existing endpoints

```
GET  /api/agents
  →  unchanged + new field `notes_markdown_count`: int  (count of group's runs with non-empty notes)
```

`GET /runs/:id/summary` adds:

```
{
  ...,
  metrics: {<metric_name>: float},   # aggregate from envelope.metadata.metrics
  notes_markdown: str,
  parent_run_id: str | null,         # already present, just confirming
  algorithm_class: str | null        # already present
}
```

### 4.3 Children endpoint (existing, used by §5)

```
GET  /runs/:id/children
  →  {"run_id": str, "children": [RunSummary, ...]}
```

The universal `Agents` tab (Brief 15) consumes this. Each child has
`parent_run_id == :id`.

## 5. Algorithm event payload extensions (Brief 14)

These payload extensions land in the algorithms themselves; the dashboard
consumes them. Brief 14 covers the implementation; per-algorithm briefs
consume the new fields.

### 5.1 `TalkerReasoner.algo_start.payload` adds:

```python
"tree": {
    "name": str,
    "purpose": str,
    "rootId": str,
    "nodes": [
        {"id": str, "title": str, "prompt": str,
         "terminal": bool, "parent_id": str | None},
        ...
    ]
}
```

### 5.2 `AutoResearcher` per-iteration payload adds:

```python
"attempt_index": int          # which of the n parallel attempts emitted this
```

And a new `algo_emit` kind `"plan"` for the planner output:

```python
kind = "plan"
payload = {"attempt_index": int, "plan": ResearchPlan.model_dump()}
```

### 5.3 `OPRO` emits algorithm events (Q7)

OPRO becomes a first-class algorithm with its own pinned `_algo_run_id`
(mirroring `EvoGradient.session()`). Events:

```
algo_start: {"params": [str], "history_window": int, "max_retries": int}
iteration phase="propose": {
  "iter_index": int,
  "step_index": int,         # global step counter inside fit()
  "param_path": str,
  "candidate_value": str,
  "history_size": int
}
iteration phase="evaluate": {
  "iter_index": int,
  "step_index": int,
  "param_path": str,
  "candidate_value": str,
  "score": float,
  "accepted": bool
}
algo_end: {"steps": int, "best_score": float, "final_values": {<param>: str}}
```

When invoked by `Trainer.fit()`, OPRO opens a *child* algorithm run via
`_enter_algorithm_run` so the OPRO run is a synthetic child of the
Trainer run. This way OPRO has its own page (per Q7) but is still
discoverable from the parent trainer.

### 5.4 `metrics` field on `OperadOutput.metadata`

When `evaluate()` runs, the envelope `metadata` adds:

```python
"metrics": {<metric_name>: float}
```

The dashboard observer projects this into `RunSummary.metrics` and into
per-invocation rows. Used by Briefs 03, 04, 14.

## 6. URL state conventions

- `?sort=<col>,<dir>` — table sort.
- `?cols=<col1>,<col2>,...` — visible columns (overrides storage).
- `?compare=<runId1>,<runId2>` — selected runs for compare (used by
`/experiments` page; Brief 04 wires the multi-select to push this).
- `#section=<id>` — opens a `CollapsibleSection` with matching id on
load (Brief 03).
- `?attempt=<n>` — for AutoResearcher, scopes the Attempts tab to one
attempt (Brief 12).
- `?dim=<axis_x>,<axis_y>` — Sweep heatmap axis selection (Brief 05).

All URL params are read by hooks under `apps/frontend/src/hooks/use-url-state.ts`
(create if missing, single canonical place).

## 7. Storage keys (localStorage)

Naming convention: `operad.dashboard.<feature>.<scope>`.

- `operad.dashboard.runtable.cols.<storageKey>` — column visibility per
table.
- `operad.dashboard.sidebar.collapsed` — existing.
- `operad.dashboard.sidebar.groupBy.<rail>` — sidebar grouping override.
- `operad.dashboard.compare.runs` — sticky compare selection (cleared
on full page navigation).

## 8. Forbidden patterns

These are tempting and wrong. Do not do them.

1. **Per-component color computation.** Always go through `hashColor()`
  or `--qual-N`. No `hsl(${id % 360}, ...)` in any component.
2. **One-point-per-series in `MultiSeriesChart`.** Each series must have
  ≥2 points or `MultiSeriesChart` will not render. If you have one
   point per run, flatten into one series with N points; if you really
   need single-point markers, use a scatter primitive (Brief 04 supplies
   one wrapped on top of the same chart).
3. **Backwards-compat aliases.** Do not export `RunsTable` from the new
  `RunTable` file. Do not keep `CostTab.tsx`. Do not redirect old
   routes.
4. **Inline `<table>` per page.** All tables go through `RunTable` with
  appropriate columns and `storageKey`. The two narrow exceptions
   (the parameters list inside `TrainableParamsBlock`, the hash list in
   `ReproducibilityBlock`) are documented in their respective briefs.
5. **Drag/resize panel grids.** Out of scope; the static `PanelGrid`
  primitive is what every brief uses.
6. **A new accordion variant on every page.** The `CollapsibleSection`
  primitive is shared.
7. **Reaching across briefs.** If you need a type/component owned by
  another brief, add it to this contracts document and ask the parent
   agent to bump the relevant briefs in lockstep.

## 9. Glossary of routes

For quick reference; all paths are absolute.


| Path                                        | Renders                                                         | Brief         |
| ------------------------------------------- | --------------------------------------------------------------- | ------------- |
| `/agents`                                   | Agents index                                                    | 04            |
| `/agents/:hash`                             | Group page (Overview tab)                                       | 04            |
| `/agents/:hash/runs`                        | Group page (Invocations)                                        | 04            |
| `/agents/:hash/metrics`                     | Group page (Metrics)                                            | 04            |
| `/agents/:hash/train`                       | Group page (Train) — only when trainable                        | 04            |
| `/agents/:hash/graph`                       | Group page (Graph)                                              | 04            |
| `/agents/:hash/runs/:runId`                 | Single-invocation Overview                                      | 03            |
| `/agents/:hash/runs/:runId/graph`           | Single-invocation Graph                                         | 03            |
| `/agents/:hash/runs/:runId/metrics`         | Single-invocation Metrics (table)                               | 03            |
| `/agents/:hash/runs/:runId/drift`           | Single-invocation Drift (when present)                          | 03            |
| `/algorithms`                               | Algorithms index                                                | 02            |
| `/algorithms/:runId`                        | Algorithm-class-specific layout (resolved via JSON)             | 02 + per-algo |
| `/training`                                 | Training index                                                  | 13            |
| `/training/:runId`                          | Training detail (Trainer-shaped)                                | 13            |
| `/opro`                                     | OPRO index (Q7 — own page)                                      | 16            |
| `/opro/:runId`                              | OPRO detail                                                     | 16            |
| `/runs/:runId`                              | **Removed.** Old legacy route is deleted (no backwards compat). | 02            |
| `/benchmarks`, `/cassettes`, `/experiments` | Unchanged                                                       | —             |


## 10. Open contract questions

If a brief surfaces something that needs to be added here, post it in
your PR with the suggested contract change. Anticipated additions:

- Whether `RunTable` should support keyboard nav (`j/k`, `o` to open).
*Default: yes, but defer if blocked.*
- Whether the `Agents` universal tab paginates or virtualizes for
222-cell sweeps. *Default: pager + grouped-by-hash collapse, per
Brief 15.*
- Whether OPRO should appear in the global rail as a separate icon, or
under the Algorithms rail. *Q7 says "own page"; Brief 16 reads this
as a top-level rail.*