# 04 — Agent group page redesign

**Stage:** 3 (parallel; depends on Briefs 01, 02; sister of Brief 03)
**Branch:** `dashboard-redesign/04-agent-group`
**Depends on:** Brief 01, Brief 02

## Goal

Redesign `/agents/:hash` and the Agents index `/agents`. The group
page now answers "how does this agent instance behave across all its
invocations?" with: a tight Overview, a rich Invocations table (the
W&B-style table you wanted), a Metrics tab (renamed from Cost) showing
*all* metrics over time, and a Train tab (renamed from Drift, only
visible when trainable parameters exist) that visualizes parameter
evolution and prompt drift in one place. The Agents index is replaced
with a single `RunTable` of groups, sortable, with sparklines.

## Read first

- Your routes: `/agents`, `/agents/:hash`, `/agents/:hash/runs`,
  `/agents/:hash/metrics`, `/agents/:hash/train`, `/agents/:hash/graph`.
  Brief 02 owns the route table; this brief fills the tab bodies.
- `proposal.md` §3.1 and §3.2.
- `apps/frontend/src/dashboard/pages/AgentsIndexPage.tsx` — current
  index, will be replaced.
- `apps/frontend/src/dashboard/pages/AgentGroupPage.tsx` — current
  group page, will be replaced.
- `apps/frontend/src/dashboard/pages/AgentGroupSubpages.tsx` — current
  Cost / Drift / Runs subpages, will be replaced.
- `apps/frontend/src/components/panels/section-sidebar/agents-tree.tsx`
  — sidebar; this brief tightens the row visuals (color dot, sparkline)
  in tandem with the index.
- `00-CONTRACTS.md` §2.1 (`RunTable`), §2.2 (`MetricSeriesChart`),
  §4.1 (new endpoints `/api/agents/:hash/metrics`,
  `/api/agents/:hash/parameters`).
- `INVENTORY.md` §1 (`hash_content`), §13 (`langfuse_url`),
  §20 (reproducibility hashes), §21 (Parameter family + `mark_trainable`
  + parameter constraint), `operad/optim/README.md` (which fields are
  trainable in practice).

## Files to touch

Create:

- `apps/frontend/src/dashboard/pages/AgentsIndexPage.tsx` — replace
  contents.
- `apps/frontend/src/dashboard/pages/AgentGroupPage.tsx` — replace
  contents.
- `apps/frontend/src/dashboard/pages/AgentGroupOverviewTab.tsx`
- `apps/frontend/src/dashboard/pages/AgentGroupRunsTab.tsx` — the
  W&B-style invocations table.
- `apps/frontend/src/dashboard/pages/AgentGroupMetricsTab.tsx`
- `apps/frontend/src/dashboard/pages/AgentGroupTrainTab.tsx`
- `apps/frontend/src/dashboard/pages/AgentGroupGraphTab.tsx`
- `apps/frontend/src/components/agent-view/group/identity-card.tsx`
  — the flat identity card used at the top of Overview.
- `apps/frontend/src/components/agent-view/group/parameter-evolution.tsx`
  — the parameter-history visualization for Train tab.
- `apps/frontend/src/components/agent-view/group/parameter-diff-panel.tsx`
  — diff between two parameter values (text or numeric).
- `apps/frontend/src/components/ui/metric-series-chart.tsx`
  (per `00-CONTRACTS.md` §2.2) — wrapper around `MultiSeriesChart`
  with the bug-fixed multi-point shape and "you are here" highlight.

Edit:

- `apps/frontend/src/components/panels/section-sidebar/agents-tree.tsx`
  — apply the per-row palette from Brief 01 (color dot is now
  `hashColor(hash_content)` rounded to the curated palette; sparkline
  column shows `latencies`).
- `apps/frontend/src/dashboard/pages/AgentGroupSubpages.tsx` — DELETE.

## Page anatomy

### Index `/agents`

```
─── KPI strip (panel section "Agents") ─────────────────────────────
 67 agents      1,457 invocations      2.1M tokens     $1.23      3 errors

─── group table (RunTable primitive) ──────────────────────────────
[●●][State][Class             ][hash    ][# inv][last seen][p50 ms][tokens][cost][errors][sparkline]
[●●][live ][Reasoner          ][9dfd…  ][222  ][live     ][1,420 ][320k  ][$0.12][0    ][▁▃▆▇▆▃▁ ]
[●●][ok  ][Pipeline          ][7f3a…  ][12   ][2m ago   ][3,200 ][45k   ][$0.04][0    ][▆▆▇▇▇▆▆ ]
…
```

Default sort: `last_seen` desc. Columns toggleable; storage key
`agents-index`.

Row click → `/agents/:hash`. Multi-select disabled (compare flow on the
group page).

### Group page `/agents/:hash`

The page chrome (Brief 02 already supplies):

```
─── breadcrumb ────────────────────────────────────────────
Agents › Reasoner › 9dfd19a942… [● live | ok | error]

─── tab strip ────────────────────────────────────────────
[ Overview ] [ Invocations 222 ] [ Metrics ] [ Train ] [ Graph ]
                                              ^conditional
```

#### Overview tab

```
─── identity card (flat) ─────────────────────────────────
Reasoner                                       hash 9dfd19a942…
"You answer science questions for a curious general reader."
Rules: 2     Examples: 0     Trainable: 1 (rules)

─── KPIs (panel section "Activity") ─────────────────────
[ 222 runs ] [ 100% ok ] [ 1.4s p50 ] [ 320k tokens ] [ $0.12 ] [ live ]

─── headline chart (1 panel, full width) ────────────────
Latency × invocation
(one MultiSeriesChart series, N points, bar/line, colored by group hash)

─── slim recent runs (last 5; link to Invocations tab) ──
[●][State][Run     ][started ][latency][cost]
…
```

Three rules:
- **No multi-card "Definition" grid** here either. The flat identity
  card replaces it. Detailed config is on the *invocations* themselves
  (Brief 03 page).
- **Headline chart is one panel**, not three. Tokens and cost are
  available as extra panels in the Metrics tab.
- The recent-runs strip ends with "View all 222 →" linking to the
  Invocations tab.

#### Invocations tab — the W&B-style rich table

`RunTable` with these default columns:

```
[●][State][Run id][Started][Latency][Prompt tok][Compl tok][Cost][Backend][Model][Sampling][hash_input][hash_prompt][hash_output_schema][Notes]
```

All sortable. Default sort `started_at` desc. Column visibility
toggleable; storage key `agent-group-runs:<hash>`.

Behaviors:
- Click a row → `/agents/:hash/runs/:runId`.
- Multi-select (shift-click) — when ≥2 selected, a `Toolbar` slides in
  at the top with: `(N selected)  Compare → /experiments?runs=…  Clear`.
  Q3 says skip the side drawer; we push to the existing
  `/experiments` page.
- The "Notes" column renders truncated Markdown (first 60 chars).
  Editing happens on the single-invocation page (Brief 03).
- The "Sampling" column shows `T={temp} top_p={p} max_tok={n}` compact
  format.
- The hash columns are HashTag chips; clicking copies. Hashes that
  differ from the most recent invocation are colored
  `--color-warn` (drift signal).
- `Backend` and `Model` come from the leaf-config fallback path the
  backend already implements (`_leaf_backend_fallback` in
  `agent_routes.py`).

Group header (when `groupBy` enabled): default off; user toggles to
group rows by `model`, `backend`, or `hash_prompt`.

#### Metrics tab — every metric across invocations

Replaces Cost. Renders a `PanelGrid cols={2}` of `MetricSeriesChart`s,
one per metric. Default metrics:

- Latency × invocation (ms)
- Prompt tokens × invocation
- Completion tokens × invocation
- Cost × invocation (USD)
- Error rate (rolling 5)
- Output schema validation rate (1 if `hash_output_schema` matches the
  declared schema, else 0; rolling)

Plus all custom metrics surfaced via `summary.metrics` (Brief 14
populates this from `OperadOutput.metadata.metrics`):

- For each `metric_name` in any invocation's `metrics` dict, render a
  panel.
- Default reference line = group p50 (faint dashed).

The chart is `MetricSeriesChart` (Brief 01 / `00-CONTRACTS.md` §2.2):
single multi-point series, ordered by invocation index, colored by
`hashColor(group.hash_content)`. The "you are here" highlight is
unused on the group page (it's used by Brief 03).

Top of tab: a panel section "Cost vs latency" (one `MetricSeriesChart`
with x = `latency`, y = `cost`, scatter mode — a circle per invocation).
Same shape for "Tokens vs latency". The previous Cost tab's two
scatters become this one section.

#### Train tab — parameter evolution and drift in one place

Conditional: tab is hidden when
`meta.trainable_paths.length === 0 && drift.length === 0`.

Layout:

```
─── KPI strip ────────────────────────────────────────
[ trainable params: 3 ] [ values seen: 8 ] [ drift events: 12 ]
[ optimizer history: opro/8 ] [ best score: 0.91 ]

─── parameter evolution (one panel per Parameter path) ─
┌── rules (RuleListParameter)  · 4 distinct values seen ──┐
│ x = invocation index                                    │
│ Each Parameter value gets its own row (lane); cells are │
│ colored by hashColor(value_hash); active value's lane  │
│ has a bold dot at each x where it was used.             │
│                                                          │
│ Click a value cell → ParameterDiffPanel slides under    │
│ the panel showing diff against the previous accepted   │
│ value (or against the initial value).                  │
└─────────────────────────────────────────────────────────┘

[ task (TextParameter) ] [ temperature (FloatParameter) ]
…

─── drift events (existing DriftBlock, demoted) ─────────
12 epochs of prompt drift recorded (PromptDrift callback) …
```

`ParameterEvolution` data source: the new
`GET /api/agents/:hash/parameters` endpoint (Brief 14, contracts
§4.1). Each parameter path has a list of `(run_id, value, hash)` rows.

`ParameterDiffPanel`:
- Text params (TextParameter, RuleListParameter): use `PromptDriftDiff`
  (existing chart) to show before/after with red/green strikethroughs.
- Float / Categorical params: render a small line of "previous → next
  (delta)" with colored arrow.
- ConfigurationParameter: render a per-key diff using
  `KeyValueGrid` with side-by-side columns.

Promote-to-training CTA: when `is_trainer === false` and trainable
params exist, show a button at the top of the tab:

```
[ Promote to training run → /training/new?seed=:hash ]
```

The button is currently dead (no `/training/new` page); link to the
existing experiments page or render it disabled with a tooltip "Coming
soon — see Brief 13" to keep scope tight.

#### Graph tab

Mounts `<AgentFlowGraph>` of the most recent invocation in the group.
For multi-leaf agents (Pipeline, Sequential, Parallel), this is the
useful view; for single-leaf, the Brief 01 single-node fallback handles
it.

## Multi-point series fix

`useRunSeries` in the old `AgentGroupPage` is the bug. Replace with the
multi-point shape:

```ts
function useGroupSeries(
  runs: RunSummary[],
  metric: "latency" | "tokens" | "cost",
  groupHash: string,
): MetricSeriesChartProps {
  const points = useMemo(() => {
    return [...runs]
      .sort((a, b) => a.started_at - b.started_at)
      .map((r, i) => ({
        x: i + 1,
        y: metric === "latency" ? r.duration_ms
          : metric === "tokens" ? r.prompt_tokens + r.completion_tokens
          : r.cost?.cost_usd ?? null,
        runId: r.run_id,
      }));
  }, [runs, metric]);
  return { points, identity: groupHash, height: 200 };
}
```

One series, N points, ordered by start time, colored by
`hashColor(groupHash)`. The colored line is now visible.

The Cost tab's scatter (`useScatter`) similarly flattens to one series
of N points; the chart prop `scatter` is honored to render circle
markers instead of lines.

## Design alternatives

### A1: One Metrics tab vs. separate Latency / Cost tabs

- **(a)** One Metrics tab with all panels (recommended).
- **(b)** Latency / Cost / Custom-metrics each as separate tabs.
  **Reject:** more clicks, less density.

### A2: Where parameter evolution lives

- **(a)** Train tab (recommended; user's spec).
- **(b)** A new "Parameters" tab. **Reject:** the Train tab is the
  natural home — proposal §3.2 calls this out.

### A3: How to render multi-value parameters across invocations

- **(a)** Lane-per-value chart (recommended). Each distinct value gets
  its own y-lane; dots show when it was active. Reads like a Gantt
  chart of the parameter's history.
- **(b)** A timeline of state transitions. Less dense but cleaner; if
  there are >8 distinct values, the lane chart gets unreadable. **Use
  as fallback** when distinct-value count > 8.
- **(c)** Just a table of (run_id, value, accepted). **Reject:** doesn't
  expose the temporal pattern.

### A4: Multi-select and compare on Invocations tab

- **(a)** Push to `/experiments?runs=…` (recommended; Q3 = skip
  drawer).
- **(b)** Inline overlay panel above the table. **Reject:** crowds the
  table.

### A5: Per-row Notes preview format

- **(a)** Truncated Markdown text (recommended; 60 chars).
- **(b)** Notes count badge ("📝 2 lines"). **Reject:** less informative.

## Acceptance criteria

- [ ] `/agents` renders one `RunTable` of groups with the columns
  above; sortable; sparkline column visible; click navigates.
- [ ] `/agents/:hash` Overview shows the flat identity card, KPI
  strip, single headline chart with **visible lines** (not just
  hover dots), and a slim recent-runs list.
- [ ] `/agents/:hash/runs` shows the full Invocations table with all
  contracted columns; multi-select pushes to `/experiments`.
- [ ] `/agents/:hash/metrics` shows one panel per metric, including
  custom metrics from `summary.metrics`. Series have visible lines.
- [ ] Cost-vs-latency scatter exists in Metrics tab.
- [ ] `/agents/:hash/train` shows parameter evolution lanes for each
  trainable path. Clicking a value cell opens the `ParameterDiffPanel`.
- [ ] Train tab is hidden when no trainable paths and no drift.
- [ ] `/agents/:hash/graph` renders the agent flow graph, including
  the single-leaf fallback.
- [ ] Sidebar Agents tree rows use the curated palette dot.
- [ ] No `useRunSeries` 1-point bug remains anywhere.
- [ ] `pnpm test --run` green.
- [ ] `make build-frontend` green.
- [ ] Manual smoke: examples 01 (multi-leaf) and 03 (trainable) both
  render without errors.

## Test plan

- **Unit:** `agent-group-overview-tab.test.tsx`,
  `agent-group-runs-tab.test.tsx`, `agent-group-metrics-tab.test.tsx`,
  `agent-group-train-tab.test.tsx`. Each tests rendering with realistic
  fixture data plus empty-state handling.
- **Series fix:** `multi-series-chart.test.tsx` (extended from Brief
  01) with a 10-run group: assert `<path d>` contains an `L` segment.
- **Parameter evolution:** `parameter-evolution.test.tsx` with three
  values across five runs.
- **Visual:** before/after screenshots of `/agents/:hash` (chosen:
  example 03's `LengthTaskOPRO` group, which has trainable params).

## Out of scope

- Single-invocation page (Brief 03).
- Backend `/api/agents/:hash/metrics` and `/api/agents/:hash/parameters`
  implementations (Brief 14).
- LayoutResolver / route shape (Brief 02).
- Compare side drawer (Q3 — skipped).
- New training-run launch flow (Brief 13 has the Training rail).

## Hand-off

PR body must include:
1. Acceptance-criteria checklist with file:line evidence.
2. Before/after screenshots of `/agents`, `/agents/:hash`, and
   `/agents/:hash/train` for the LengthTaskOPRO group.
3. Confirmation that the legacy 1-point series bug is gone.
4. List of any UI strings that should be added to the design's voice
   guidelines (Tone of empty states, etc.).
