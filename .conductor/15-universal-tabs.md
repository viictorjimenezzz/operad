# 15 — Universal `Agents` and `Events` tabs

**Stage:** 3 (parallel; depends on Briefs 01, 02)
**Branch:** `dashboard-redesign/15-universal-tabs`

## Goal

Build the two tabs that every algorithm view in the redesign declares
last: **Agents** (the synthetic-children index that lets users jump
into the agent fleet an algorithm spawned) and **Events** (a
keyboard-navigable, filterable timeline that replaces the current
free-form `EventTimeline`).

These two tabs are the most reused components in the entire redesign.
Get them right and every algorithm benefits.

## Read first

- `00-CONTRACTS.md` §2.1 (RunTable), §6 (URL state — `?event=`),
  §9 (route map).
- Brief 02 — created stub components for `AgentsTab` and `EventsTab`;
  this brief fills them.
- `apps/dashboard/operad_dashboard/app.py:191-216` — the existing
  `/runs/:id/{children,parent,tree}` endpoints.
- `apps/dashboard/operad_dashboard/runs.py:155-156` —
  `RunRegistry.list_children()`.
- `apps/frontend/src/components/panels/event-timeline.tsx` — current
  free-form list, will be deprecated.
- `apps/frontend/src/hooks/use-runs.ts` — `useRunEvents`, etc.
- `apps/frontend/src/components/ui/run-table.tsx` (Brief 01) — the
  primitive Agents tab consumes.
- `INVENTORY.md` §13 (observers and events).

## Files to touch

Create:

- `apps/frontend/src/components/agent-view/page-shell/agents-tab.tsx`
  (Brief 02 created the stub; this brief fills it).
- `apps/frontend/src/components/agent-view/page-shell/events-tab.tsx`
  (same).
- `apps/frontend/src/components/agent-view/page-shell/event-row.tsx`
  (the event renderer used by the Events tab).
- `apps/frontend/src/hooks/use-children.ts` — TanStack hook for
  `/runs/:id/children`.
- Tests:
  - `apps/frontend/src/components/agent-view/page-shell/agents-tab.test.tsx`
  - `apps/frontend/src/components/agent-view/page-shell/events-tab.test.tsx`

Edit:

- `apps/frontend/src/components/registry.tsx` — register `AgentsTab`
  and `EventsTab` for JSON consumption.
- `apps/frontend/src/components/panels/event-timeline.tsx` — DELETE
  after consumers migrate. (Existing per-algorithm layouts that
  reference `EventTimeline` are updated by Brief 02 to use `EventsTab`.)

## `AgentsTab` — synthetic-children navigator

```ts
interface AgentsTabProps {
  runId: string;
  /** Default grouping. */
  groupBy?: "hash" | "none";  // default: "hash"
  /** Algorithm-specific extra columns to show.
   *  Built-in keys: "score", "axisValues", "attempt_index", "gen", "individual_id". */
  extraColumns?: string[];
  /** Override the default empty-state copy. */
  emptyTitle?: string;
  emptyDescription?: string;
}
```

Fetches `/runs/:runId/children` (existing endpoint). Renders a
`RunTable` with these default columns:

```
[●][State][Agent class][hash_content][# inv][started][last seen][latency p50][cost]
```

Plus extra columns per `extraColumns`. The `axisValues` column reads
`child.summary.metadata.algorithm_axis_values` (set by Sweep when the
backend tags it; if absent the column shows nothing). `score` reads
`child.summary.metrics.score` if present. `attempt_index`, `gen`,
`individual_id` come from the child's `algorithm_metadata` (set by
backend when applicable).

### Grouping

`groupBy === "hash"` (default):
- Row header per `hash_content`. Header shows class name + count + a
  representative sparkline + aggregate p50 latency.
- Children are listed under the header in default-collapsed groups
  (chevron expand).
- Clicking a child navigates to `/agents/:hash/runs/:runId`.
- Clicking the group header navigates to `/agents/:hash`.

`groupBy === "none"`:
- Flat list of children. Used by Sweep override.

A "Group / Ungroup" toggle in the toolbar above the table.

### Pagination

With 222 cells (typical for a sweep), virtualize is not yet warranted,
but **paginate** at 50 by default. Storage key for column visibility:
`agents-tab:<runId>`.

### Empty state

When `children.length === 0`:

```
EmptyState
  title="no agent invocations yet"
  description="this algorithm hasn't spawned synthetic children yet — the first algo_emit lands as soon as the algorithm enters its main loop"
```

## `EventsTab` — filterable timeline

```ts
interface EventsTabProps {
  runId: string;
  /** Default kind filter. Algorithms set this. */
  defaultKindFilter?: string[];
  /** Default agent_path filter (per-leaf swimlane). */
  defaultPathFilter?: string;
}
```

### Layout

```
─── filter strip ─────────────────────────────────
[ Search… ] [ Kind: any ▾ ] [ Path: any ▾ ] [ Severity: any ▾ ]
[ Show: agent_event | algo_event | both ▾ ]   [ Live ▢ ]

─── events list (virtualized vertically) ────────
12:42:01.123 algo_event Beam algo_start                {n: 5, top_k: 2}
12:42:02.118 agent_event Reasoner.0 start
12:42:02.812 agent_event Reasoner.0 end                latency 694ms
12:42:02.819 agent_event Reasoner.1 start
…

─── selected event detail (right pane, slides in on click) ────
algo_event Beam candidate
  iter_index: 0
  candidate_index: 3
  score: 0.84
  text: "<Markdown rendered…>"
  metadata: { … }
[ Open in Langfuse → … ]
```

Each event row is a single line with timestamp, type, agent_path or
algorithm_path, kind, and a one-line payload summary. Clicking opens
the right detail pane; the URL updates with `?event=<idx>` (where
`idx` is the index in the events list).

### Filters

- **Kind:** multi-select. Default = full set; algorithm-specific
  defaults narrow to the salient kinds (sweep → `cell`; debate →
  `round`; evogradient → `generation`; trainer → `batch_end`,
  `gradient_applied`, `iteration`).
- **Path:** dropdown of unique `agent_path` values seen in this run.
  Selecting one filters to that path's events — effectively a
  per-leaf swim-lane.
- **Severity:** present only when the run has gradient events
  (Trainer); filter `gradient_applied` events by severity bucket.
- **Type:** radio for `agent_event` / `algo_event` / both (default:
  both).

URL state syncs all four filters (`?kind=`, `?path=`, `?sev=`,
`?type=`).

### Keyboard nav

- `j` / `↓` next event.
- `k` / `↑` previous event.
- `Enter` opens the detail pane.
- `Esc` closes the detail pane.
- `/` focuses the search input.

### Live updates

When the `Live` checkbox is on (default if the run is `running`), new
events stream in via SSE and the list auto-scrolls (unless the user
has scrolled up — then a "new events ↓" pill appears).

### Performance

For runs with >1000 events (training runs, big sweeps), use
`@tanstack/react-virtual` (which is already a transitive dep via
`recharts`; verify with `pnpm why`). Render only the visible window.

## Component reuse

`EventRow` is the row renderer. It dispatches per `kind` to a small
inline summary:

```ts
const SUMMARIZERS: Record<string, (e: Envelope) => ReactNode> = {
  algo_start: (e) => `${pretty(e.algorithm_path)} ${pluck("n", "max_iter", "rounds")(e)}`,
  generation: (e) => `gen ${e.payload.gen_index}: best ${e.payload.best?.toFixed(2)}`,
  candidate: (e) => `cand #${e.payload.candidate_index} score ${fmt(e.payload.score)}`,
  cell: (e) => `cell #${e.payload.cell_index} ${shortParams(e.payload.parameters)}`,
  round: (e) => `round ${e.payload.round_index} mean ${mean(e.payload.scores).toFixed(2)}`,
  iteration: (e) => `iter ${e.payload.iter_index} ${e.payload.phase} ${fmt(e.payload.score)}`,
  gradient_applied: (e) => `severity ${e.payload.severity?.toFixed(2)} → ${e.payload.target_paths?.join(", ")}`,
  batch_end: (e) => `epoch ${e.payload.epoch} batch ${e.payload.batch} loss ${e.payload.train_loss?.toFixed(3)}`,
  start: (e) => `${pretty(e.agent_path)} start`,
  end: (e) => `${pretty(e.agent_path)} end (${fmtMs(e.metadata?.latency_ms)})`,
  // …
};
```

When no summarizer exists, render `${kind} (payload omitted)` with the
expanded JSON in the detail pane.

## Design alternatives

### A1: Group-by-hash default for AgentsTab

- **(a)** Yes (recommended; aligns with Q1 and the Sweep override).
- **(b)** No (flat default). **Reject:** 222 cells flatten reads.

### A2: Where the EventsTab detail pane lives

- **(a)** Slide-in right pane (recommended; matches W&B's run-side
  inspectors).
- **(b)** Modal. **Reject:** breaks deep-link flow.
- **(c)** Inline expansion below the row. Possibly; more like a code
  diff in your IDE. Defer; we can add as a "Compact" mode later.

### A3: Virtualization

- **(a)** Use `@tanstack/react-virtual` past 500 rows (recommended).
- **(b)** Always paginate. **Reject:** event timelines benefit from
  scroll continuity.

## Acceptance criteria

- [ ] `AgentsTab` fetches `/runs/:runId/children`, renders a
  `RunTable`, supports `groupBy="hash"` / `"none"`, click-through
  to `/agents/:hash[/runs/:runId]`.
- [ ] `EventsTab` renders all events with type/kind/path/severity
  filters; URL state syncs.
- [ ] Keyboard nav works (`j/k`, `Enter`, `Esc`, `/`).
- [ ] Live update works while a run is `running`; auto-scroll respects
  user scroll-up.
- [ ] Severity filter only appears when `gradient_applied` events
  exist.
- [ ] Each algorithm's default kind filter is applied (verify by
  navigating to a Sweep run and seeing the Events tab default-filtered
  to `cell`).
- [ ] `EventTimeline` (the legacy component) is no longer referenced
  by any layout JSON.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `agents-tab.test.tsx` (groupBy modes, navigation),
  `events-tab.test.tsx` (filters, keyboard nav, virtualization).
- **Schema:** verify `EventsTab` and `AgentsTab` are in the JSON
  registry and parse `defaultKindFilter` / `groupBy` / `extraColumns`
  correctly.
- **Manual smoke:** open `/algorithms/<sweepRunId>` and verify the
  Agents tab collapses 27 cells under one Reasoner header; expand;
  click a child to navigate.

## Out of scope

- Per-algorithm tab specifics (Briefs 05-12, 13, 16).
- Backend changes (Brief 14 already exposes `algorithm_metadata` on
  child summaries).
- Compare drawer (Q3 — skip).

## Hand-off

PR body with:
1. Acceptance-criteria checklist.
2. Screenshots of `AgentsTab` (grouped + ungrouped), `EventsTab`
   (all + sweep-filtered + with detail pane open).
3. Performance smoke result for a 222-event run (target: <100ms
   initial render with virtualization).
