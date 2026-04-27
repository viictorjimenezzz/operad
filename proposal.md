# Dashboard redesign — proposal v2

This supersedes the earlier proposal entirely. It is grounded in a full read
of the frontend (`apps/frontend/src/`), the dashboard backend
(`apps/dashboard/operad_dashboard/`), every algorithm and the events it
emits (`operad/algorithms/`, `operad/optim/optimizers/`, `operad/train/`),
and the live state of the dashboard at `127.0.0.1:7860` after running
examples 01–04.

The plan addresses each of your complaints with a concrete change and adds
many further ideas anchored to real data we already produce. It deliberately
breaks backwards compatibility wherever the existing surface gets in the
way (per `METAPROMPT.md` line 36).

---

## 0. Two findings that reshape the plan

Surfacing these first because they invalidate the earlier proposal's
framing.

### 0.1 Every per-algorithm JSON layout is dead code

`apps/frontend/src/layouts/{beam,debate,evogradient,selfrefine,sweep,trainer,verifier}.json`
exist, are Zod-validated at module load, and are never used.
`resolveLayout()` in `apps/frontend/src/layouts/index.ts` only has a single
caller — its own unit test. The route table in
`apps/frontend/src/dashboard/routes.tsx` mounts the *same* `RunDetailLayout`
for `/algorithms/:runId`, `/training/:runId`, `/agents/:hashContent/runs/:runId`,
and the legacy `/runs/:runId`. `RunDetailLayout`'s tab list is hard-coded
(Overview / Graph / Invocations / Cost / Train? / Drift?) and its Overview
tab always parses `layouts/agent/overview.json`.

**Consequence:** "the algorithm view looks like an agent view" is not a
design choice — it's a wiring bug. The fix is to pick the layout based on
`summary.algorithm_class` (or `algorithm_path`) and render its tab tree
directly, replacing `runDetailChildren` with one route per rail-shape.

### 0.2 The "colored line" in agent group view is a degenerate series

`useRunSeries()` in `apps/frontend/src/dashboard/pages/AgentGroupPage.tsx`
emits one series per run with one point. `MultiSeriesChart` renders each
series as `<path d="M x y">` — no `L` segment — which the browser draws
as nothing. What you see is hover dots only. The fix is to flatten into
**one** series across runs, with one point per *invocation* (sorted by
start time), colored by `hashColor(group.hash_content)`, and add a `Pill`
or `dot` per row. Same fix for `AgentGroupCostTab`.

---

## 1. Visual & interaction language (the W&B fidelity gap)

The screenshots tell us what we are still missing visually. The repo
already has the primitives (`PanelCard`, `PanelGrid`, `PanelSection`,
`HashTag`, `StatusDot`, `Sparkline`, `MultiSeriesChart`, `hashColor`).
What it lacks is consistent application.


| W&B move                         | Today                                                                                               | Change                                                                                                                                                                                                                                                                                                          |
| -------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Color-by-identity, pervasive** | `hashColor` exists; only used in `HashTag` and `Sparkline`                                          | Use `hashColor(hash_content)` for the group dot in the sidebar **and** for every series, axis legend, table swatch downstream. Add a 4-px left "color rail" to the active row in tables.                                                                                                                        |
| **Tight rich tables**            | `RunsTable` is a hand-rolled `<table>` without sort, sparkline, or column toggles                   | Build one canonical `RunTable` primitive in `components/ui/run-table.tsx`: sortable headers, per-row `colorIdentity`, optional `sparkline` column, multi-select for compare, sticky header, density toggle, column visibility menu, "1-N of M" pager. Used everywhere a list of runs/invocations/cells appears. |
| **Status iconography**           | `StatusDot` already has `running/error/ended`, `pulse`                                              | Add `crashed` (long-stale running) and `queued`. Also expose a `status="finished_ok"` glyph (filled check) vs `ended` (just colored).                                                                                                                                                                           |
| **Workspace-style canvas**       | `PanelCard`s on a static `PanelGrid`                                                                | Phase-1 keep static grid; document a `PanelGrid` API that supports `cols`, `gap`, and `presets` (e.g. `"2-1"` → two-thirds + one-third). Defer drag/resize to a later phase; we get 80% of the look without it.                                                                                                 |
| **Breadcrumb-only chrome**       | `AgentChrome` already correct                                                                       | Keep, but move the inline KPIs (`ago`, `dur`, `tok`, `$`) into the canvas as a KPI row (`PanelSection.label="Run"`). The breadcrumb should be **just** crumbs + a `langfuse` link + status pill.                                                                                                                |
| **Color palette**                | `--color-accent` cyan + neutral slate + log-warn-err                                                | Add a curated 12-hue qualitative palette in `tokens.css` (`--qual-1..12`). `hashColor` already produces a deterministic hue per identity; switch its output to round into this palette so series colors look intentionally chosen, not noisy.                                                                   |
| **No big hero**                  | `AgentChrome` fits, but Overview tab still has a 2-column "Definition" duplicate of the chrome KPIs | Resolve by making the Overview's first row a **slim status strip** (state pill, 4 KPI metrics, langfuse link), then jump straight to I/O. See §3.2.                                                                                                                                                             |
| **Saved 1 minute ago**           | absent                                                                                              | Defer; we already encode state in the URL. Add a tiny "auto-saved" affordance only when we add panel-layout persistence.                                                                                                                                                                                        |


---

## 2. Three rails, one canonical sidebar

The three-rail global navigation (Agents / Algorithms / Training, plus
Benchmarks / Cassettes / Experiments / Archive in the global rail) is
already correct in `apps/frontend/src/components/panels/global-rail.tsx`
and `apps/frontend/src/components/panels/section-sidebar/section-sidebar.tsx`.
What's missing is signal.

### 2.1 Group-by-`hash_content` everywhere

- **Agents rail.** `useAgentGroups()` returns one row per `hash_content`.
Multi-invocation groups should expand to show child runs; single-invocation
groups link directly. (Current behaviour is already correct.)
- **Algorithms rail.** Group by `algorithm_class` (or `algorithm_path` —
the API returns it) and **also** by `script` so two scripts that both
use `Beam` show as separate sections. Keep run rows flat (no children),
per your spec.
- **Training rail.** Group by trainee `hash_content` (the *initial*
agent identity). Children are training attempts. A 3rd level
(`epoch_X`) opens on demand.

### 2.2 Per-row affordances

Every row, on every rail:

1. 8-px color dot from `hashColor(hash_content)` — same color used in every
  chart series and table row swatch downstream.
2. State glyph (`StatusDot` running/ended/error).
3. Mid: name (truncated middle), tags (`script`, `is_algorithm`).
4. Right: a 60×16 `Sparkline` of an algorithm-relevant signal (latencies
  for agents, terminal scores for algorithms, val_loss for training).
5. Trailing: "12s ago".

### 2.3 The W&B sidebar header

Add the `Filter | Group by | Sort | New sweep` strip above the tree
(matching screenshot 2). Each control is a `<Popover>`:

- **Filter:** by state, by tag, by min latency, by error count.
- **Group by:** override the rail's default key (`hash_content` ↔
`algorithm_class` ↔ `script`).
- **Sort:** by `last_seen` / `started_at` / `score` / `cost` / `tokens`.
- **New sweep:** opens a modal that POSTs to a (new) `/api/sweeps/launch`
endpoint — a follow-up; visually the button is there.

### 2.4 Pager + virtualization

Sweeps emit hundreds of synthetic children. The current `Pager` (already
used by `AgentsTree`) handles the parent list; **the children list under
a multi-invoked group should virtualize** with a pager too — currently
expanding a 222-child group injects 222 DOM rows.

---

## 3. Agents rail

### 3.1 Index (`/agents`)

The current `AgentsIndexPage` is a 3-column grid of `AgentGroupCard`s.
That's fine for first impressions but gives up sortability and density.

Replace with a **two-row layout**:

1. **KPI strip** at top (`PanelSection.label="Agents"`): total agents,
  total invocations, total tokens, total cost, error count across the
   project.
2. A `RunTable` (the new primitive) with columns: `[●][State][Class][hash][# invocations][last seen][p50 latency][tokens][cost][errors][sparkline]`.
  Sort by any column. Click → `/agents/:hash`. Multi-select → "Compare".

### 3.2 Group page (`/agents/:hash_content`)

Tabs you asked for, with my interpretation:


| Tab             | Visible when                                                     | Rationale                                                                                                                            |
| --------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Overview**    | always                                                           | identity + KPIs + a single multi-series chart, in that order. No section accordions.                                                 |
| **Invocations** | always                                                           | the W&B-style table you want. Same `RunTable`, but per-invocation.                                                                   |
| **Metrics**     | always (renamed from `Cost`)                                     | every numeric metric across invocations: latency, tokens, cost, plus user-supplied metric scores when present. One panel per metric. |
| **Train**       | only if `meta.trainable_paths.length > 0` (renamed from `Drift`) | parameter evolution + value diffs across invocations. The "drift" panel becomes one section inside this tab.                         |
| **Graph**       | always                                                           | `AgentFlowGraph` of the root agent (shape doesn't vary across invocations of the same instance).                                     |


#### Overview redesign (`/agents/:hash`)

Replace `AgentGroupOverviewTab`'s current "Summary KPI grid + 3 broken
charts + table" layout with:

```
[ status strip: live/ended pill · runs total · last seen · p50 latency · tokens · cost · langfuse ]

[ Identity card                       ] [ Latency × invocation chart  ]
[ class · role · task · rules · hash  ] [ ONE series, one point/invo  ]

[ Backend & sampling (1 collapsed row, click to expand) ]
```

The Identity card is `IdentityBlock` minus the section accordion — flat.
The chart is the bug-fixed multi-series chart (§0.2).

#### Invocations tab (the rich W&B-style table)

Drop the existing `AgentGroupRunsTab` table. Replace with a `RunTable`
that has these columns by default, all sortable, all toggleable from a
"Columns" menu (W&B parity):

```
[ ● ] [ Run ] [ State ] [ Started ] [ Latency ] [ Prompt tok ] [ Compl tok ] [ Cost ]
[ Backend ] [ Model ] [ Sampling ] [ hash_input ] [ hash_prompt ] [ hash_output_schema ]
[ Notes ]
```

- The leading `●` is the per-run color (deterministic from `run_id` so
rows match chart colors).
- Multi-select via shift-click; selected runs go to a **Compare drawer**
that overlays their per-invocation series in the Metrics tab.
- "Notes" column is editable inline → a `PATCH /api/runs/:id/notes`
endpoint (new, additive — see §6).

#### Metrics tab (renamed from Cost)

The current `AgentGroupCostTab` shows cost-vs-latency and tokens-vs-latency
scatters. Replace with a **panel grid of metric charts**, one panel per
metric, for *every metric we know about*:


| Metric panel                   | Source                                                                                       |
| ------------------------------ | -------------------------------------------------------------------------------------------- |
| Latency × invocation           | `RunSummary.duration_ms` (or per-leaf `latency_ms`)                                          |
| Prompt tokens × invocation     | `RunSummary.prompt_tokens`                                                                   |
| Completion tokens × invocation | `RunSummary.completion_tokens`                                                               |
| Cost (USD) × invocation        | `RunSummary.cost.cost_usd`                                                                   |
| Error rate (rolling 5)         | `status == "error"` ratio                                                                    |
| Output schema validation %     | when a `hash_output_schema` is set, count of validation passes (per `OperadOutput` envelope) |


Plus, when this group is also a child of an algorithm/training run, add
a panel for the algorithm-supplied score (e.g., metric value per
invocation when `evaluate(...)` produced one).

**New backend deltas to make this useful:**

- Persist per-invocation metric scores. Currently `metric` results live
on the `OperadOutput`'s `metadata` only when the user asks. Promote a
small `metrics: dict[str, float]` field on the envelope (already
emitted by `evaluate`) and wire it through `serialize_event`. Then
`RunInfo` aggregates metric series over time. (See §6.)

#### Train tab (renamed from Drift; conditional)

This tab is the unique-to-operad superpower. Show:

1. **Parameter evolution chart.** One `MultiSeriesChart`, x = invocation
  index, one series per `Parameter` path, y = a stable identifier of
   the value at that point (hash slug for text params, the float for
   `FloatParameter`s). For text params, the chart is a "lane" of dots
   colored by `hashColor(value)` — same color = same value.
2. **Per-parameter timeline** (one card per parameter): every value seen,
  with a colored swatch and the timestamps when it was active. Clicking
   a swatch opens a side panel with the **diff** against the previous
   value (using `operad.utils.ops.AgentDiff` rendered with `PromptDriftDiff`).
3. **Drift events** (when present): the existing `DriftBlock`, but
  demoted to one section.
4. **Promote to training run** CTA when `is_trainer == false` for this
  group: links to "create a Trainer with this hash as seed".

This replaces the current `Drift` tab name with something that actually
describes what's interesting. "Drift" is jargon; "Train" is the user
mental model.

#### Graph tab

Just `AgentFlowGraph` of the most recent invocation. No tab list inside
the tab — the inspector pane already does what's needed. Move the
`InspectorShell`'s rightmost "Edit & run" tab gating behind a feature
flag (`allow_experiment`, already on the backend).

### 3.3 Single invocation page (`/agents/:hash/runs/:runId`)

You asked for: no Invocations tab, no Train tab, Cost → Metrics, Graph
that actually works, no "Latest invocation" wording, no four-card
Definition redundancy, smaller preview with chevron expansion.

Tabs:


| Tab          | Visible when                                                                                                   |
| ------------ | -------------------------------------------------------------------------------------------------------------- |
| **Overview** | always                                                                                                         |
| **Graph**    | always                                                                                                         |
| **Metrics**  | always (renamed from Cost; for a single invocation it shows the run's metric *values*, not series — see below) |
| **Drift**    | only when this run has drift events                                                                            |


(No Invocations. No Train.)

#### Overview redesign (single-invocation)

Goal: small preview, expand for detail. Today the page dumps four cards
of metadata + a Reproducibility section + a Sister Runs card; that's
the shape of a settings page, not a "look at this run" page.

Replace with:

```
[ status strip — same shape as AgentChrome KPIs but moved into the canvas ]

[ I/O preview (large) ] [ I/O preview (large) ]
[  Input              ] [  Output              ]
[  collapsed JSON;    ] [  collapsed JSON;     ]
[  click to expand    ] [  click to expand     ]

▸ Identity              [hash · role · task]    (collapsed, expand chevron)
▸ Backend & sampling                            (collapsed, expand chevron)
▸ Examples (N)                                  (collapsed, expand chevron)
▸ Trainable parameters (N)                      (collapsed, expand chevron)
▸ Reproducibility (7 hashes)                    (collapsed, expand chevron)
▸ Sister runs (M)                               (collapsed, expand chevron)
```

Specifically:

- **Kill `InvocationsBanner`** in the single-invocation case. Its
`SingleInvocation` branch is what hard-codes "Latest invocation". The
status + I/O is enough — there's no banner to be had.
- **Reduce the four "Definition" cards to one collapsible panel.** It
has four sub-sections (Identity, Backend, Examples, Trainable) that
share one heading row "Definition" and only paint the chrome of an
expanded sub-section. This solves the "they all look the same" issue
by removing the visual repetition entirely.
- The preview-then-chevron pattern uses the existing `Section`
primitive (which `Section` already supports). Default-collapsed.
- "Sister runs" card now links back to the group view as the primary
CTA, not as a sidebar list.

#### Graph tab (single-invocation)

The interactive graph already exists (`AgentFlowGraph`, ReactFlow, pan,
zoom, MiniMap, Controls, expand/collapse composites, edge stats). The
empty state we see today on examples 01–04 is because:

- `RunSummary.has_graph: true` but `graph_json.edges: []` for the
Reasoner-only runs (correct — it has only one node).

The fix: when `nodes.length === 1 && edges.length === 0`, render the
single-node card prominently (large) instead of an empty state — that's
what an agent-with-one-leaf actually looks like and the user should see
it. Update `AgentFlowGraph`'s "no nodes" branch to "no graph captured"
only if `nodes.length === 0`.

For the multi-leaf case (example 01: planner + 3-way parallel + editor,
~5+ leaves), the graph already does the right thing; we just need to
verify the example actually emits `graph_json` (we should: every
composite calls `abuild()`).

#### Metrics tab (single-invocation, renamed from Cost)

For a single invocation, "Metrics" is **a table**, not a chart:

```
| Metric                    | Value          |
| ------------------------- | -------------- |
| latency_ms                | 1,420          |
| prompt_tokens             | 312            |
| completion_tokens         | 198            |
| cost_usd                  | $0.0042        |
| (custom) length_band      | 0.78           |
| (custom) judge_score      | 0.91           |
```

Plus, when applicable, a small "compared to group" delta column
(`+12% vs group p50`). This makes Metrics useful for both group and
single views with a single component.

---

## 4. Algorithms rail

This is where the user complaint is sharpest and where the upside is
biggest. The vision: **every algorithm gets its own view that
understands its own structure.** Today every algorithm reuses the
agent shell — wrong.

### 4.1 Wire the LayoutResolver

In `apps/frontend/src/dashboard/routes.tsx`, replace the
`runDetailChildren` array for `/algorithms/:runId` with a single
`<AlgorithmDetailLayout />` element that:

1. fetches `useRunSummary(runId)`,
2. calls `resolveLayout(summary.algorithm_path)` — the existing function
  in `apps/frontend/src/layouts/index.ts`,
3. renders the resolved layout with `DashboardRenderer`.

This unblocks the 7 dead-code layouts in one stroke. Each layout
declares its own `Tabs` element as the root, so we get tab strips
"for free" — no `runDetailChildren`-style child route table.

### 4.2 Per-algorithm tab sets and the "Agents" tab

Every algorithm gets a unified tab shape with **two universal tabs**
plus algorithm-specific tabs in between:

```
[ Overview ] [ algo-specific tabs… ] [ Agents ] [ Events ] [ Graph ]
```

- `**Agents` (NEW, universal).** Cross-cuts every algorithm. Lists the
algorithm's *synthetic children* — every inner agent invocation it
spawned — and links each row to `/agents/:hash/runs/:runId`. Backed
by `GET /runs/:runId/children` (already exists). This is the single
most powerful piece of new UX: it makes the algorithm's nested agent
fleet inspectable. Per your TalkerReasoner example, this is the
"agents" tab where clicking jumps you into the agents window.
- `**Events`.** A keyboard-nav'able chronological event timeline,
filterable by `kind` (algorithm-specific defaults: `cell` for sweep,
`round` for debate, `generation` for evo, `iteration` for
refine/researcher/talker). Backed by `useRunEvents`. Replaces the
current free-form `EventTimeline`.
- `**Graph`.** Same `AgentFlowGraph` rendering, but where it makes sense
the node tints reflect "this leaf is what powered this algorithm
step".

The algorithm-specific tabs differ per class:

#### Beam

`Overview · Candidates · Agents · Events · Graph`

- **Candidates:** ranked leaderboard from `RunInfo.candidates[]`. Score
bar, judge rationale on hover, click → that synthetic child run.
Marked with a "winner" pill the indices in `algo_end.top_indices`.
- **Overview:** KPIs `n`, `top_k`, `winner score`, `cost`, `wall time`.
Score histogram panel.

#### Debate

`Overview · Rounds · Agents · Events · Graph`

- **Rounds:** timeline of rounds, each round a 3-column card
`proposer | critic | synthesis` with the full proposal/critique
text rendered Markdown-aware. Score line chart (mean per round).
This is the existing `DebateTranscript` and `DebateRoundView`.
- **Overview:** synthesized `Answer` card prominent; rounds count;
proposer count; total cost.

#### Sweep

`Overview · Heatmap · Cells · Agents · Events · Graph`

- **Heatmap:** existing `SweepHeatmap` (auto-pick bar / matrix /
small multiples). Hover tooltip with full cell config and score;
click → the synthetic child run for that combination.
- **Cells:** the W&B `RunTable` with one row per cell — every parameter
axis as a column, plus score, status, started.
- **Add a parallel-coordinates panel** (use `recharts` `ParallelCoordinates`,
or a thin SVG one) for >2 swept params — the W&B sweep trick.
- **Cost:** the existing `SweepCostTotalizer` becomes a section inside
Overview, not its own tab.

#### EvoGradient

`Overview · Evolution · Population · Operators · Lineage · Agents · Events · Graph`

- **Evolution:** `FitnessCurve` (best/mean/worst). Already exists.
- **Population:** `PopulationScatter`, color-coded by survivor flag.
- **Operators:** `MutationHeatmap` + `OpSuccessTable`. Already exist.
- **Lineage** (NEW): a tree of survivors, each node is a generation's
best. Hover → "this individual added rule X to path Y because critic
said Z". Sourced from `RunInfo.generations[].mutations[]` (which
already carries `op`, `path`, `improved`).
- **Best individual diff** (NEW): per-generation diff of the survivor's
prompt vs previous best, using the same `PromptDriftDiff` we built
for training. This is unique to operad and is the "killer feature" of
the previous proposal — keep it.

#### SelfRefine

`Overview · Iterations · Agents · Events · Graph`

- **Iterations:** vertical ladder of `(generate → reflect → refine)`
triplets. Each iteration is one card with three columns and the
reflection's `critique_summary` shown as a quote between the columns.
Convergence threshold drawn as a horizontal line. Clicking a triplet
pops a side drawer with the full prompts and the synthetic child runs.

#### AutoResearcher

`Overview · Plan · Attempts · Agents · Events · Graph`

- **Plan** (NEW): renders the `ResearchPlan` and the retrieved evidence
collected in `_one_attempt`. Today `_one_attempt` doesn't emit the
plan — see §6 for the backend delta to expose it.
- **Attempts:** swimlane, one swim per attempt (n parallel). Per-step
reasoning, reflection, score. We need to add `attempt_index` to the
emitted `iteration` payload so we can group; today it's missing.

#### VerifierAgent

`Overview · Iterations · Agents · Events · Graph`

- **Iterations:** verify-loop list with the threshold line. Same shape
as SelfRefine but single-column.

#### TalkerReasoner (your example)

`Overview · Tree · Transcript · Decisions · Agents · Events · Graph`

- **Tree** (NEW): renders the `ScenarioTree` as a 2-D layout (NOT a
Mermaid graph — a hand-laid tree like a sitemap). Each node is a
small card with title + prompt preview. The path actually walked is
highlighted; the current node pulses. Click any node → the turn(s)
spent there.
- **Transcript:** chat-style `(user → assistant → decision)` rows. The
`decision_kind` (stay/advance/branch/finish) is colored. Each turn's
"user message" is the input, "assistant message" is from the synthetic
child of the `Assistant` agent, "navigation reason" comes from
`ScenarioNavigator`.
- **Decisions:** a small heatmap or table — for each visited node, how
many turns spent, which branches were taken.
- **Agents:** the universal tab — clicking a row jumps to the
`Assistant`/`ScenarioNavigator` invocation in the Agents rail.
This is the "linked into agents window" you described.

Backend delta to make Tree work: `algo_start` payload must carry the
serialized `ScenarioTree` (id, title, parent_id, terminal). Currently
it ships `process` and `start_node_id` only. See §6.

#### Trainer

Trainer keeps its own rail (§5). The Algorithms rail does *not* show
trainers — `GET /api/algorithms` already excludes them.

### 4.3 Algorithms index (`/algorithms`)

Replace the current "PanelCard per group, 3-col grid of small cells"
with the same `RunTable` primitive, grouped by algorithm class headers
like the screenshot:

```
▼ Group: Sweep · examples/benchmark/run.py        [3]
[ ● ] [ run_id ] [ state ] [ score ] [ runtime ] [ started ] [ cells ] [ winner cfg ]
…
▼ Group: Beam · examples/02_algorithm.py          [12]
…
```

Per-row sparkline column showing best-score-by-step (or score histogram
for Beam, val_loss for trainers, etc.). Score column sortable. Filter
by class. Live "running" rows pulse and float to the top.

---

## 5. Training rail

`/training` and `/training/:runId` route to the same dead `RunDetailLayout`
today. With §4.1 fixed, `algorithm_path == ".Trainer"` resolves to
`trainer.json`, which already declares the right shape:
`Loss · Drift · Gradients · Checkpoints · Progress · Graph · Events`.

### 5.1 Default workspace

A two-column panel grid:

```
┌─────────────────────────────┬─────────────────────────────┐
│ Loss curve (train + val)    │ LR schedule                 │
├─────────────────────────────┼─────────────────────────────┤
│ Gradient log (texts)        │ Checkpoint timeline          │
├─────────────────────────────┴─────────────────────────────┤
│ PromptDrift timeline (epoch × hash diff + changed paths) │
├──────────────────────────────────────────────────────────┤
│ Per-parameter small multiples — one card per Parameter   │
│ (hash-of-value timeline; click for diff view)            │
├──────────────────────────────────────────────────────────┤
│ Progress (epoch/batch matrix + ETA)                      │
└──────────────────────────────────────────────────────────┘
```

`TrainingLossCurve`, `LrScheduleCurve`, `GradientLog`,
`CheckpointTimeline`, `DriftTimeline`, `TrainingProgress` already exist
(see §4 of the layouts exploration). Wire them via `trainer.json`.

### 5.2 Compare mode

Multi-select two training runs in the sidebar (one trainee, several
attempts) → side-by-side overlaid loss curves + LR schedules. This is
basically W&B's group page for runs.

### 5.3 PromptTraceback viewer (NEW)

A unique-to-operad tab. `operad.optim.backprop.traceback.PromptTraceback`
is the optim-layer equivalent of a Python traceback. Surface it as a
tab `Traceback` on Trainer runs that have it persisted. Currently the
Trainer doesn't write traceback to the dashboard — see §6.

### 5.4 Studio integration

The Studio app is already a separate FastAPI; just add a Studio badge
to training runs that have a feedback callback attached, with a
deep-link button.

---

## 6. Backend deltas needed

Each delta below is **additive** and small. None require touching
`operad/` core; they're projections over `RunRegistry` or callback
emit-payload fields.

### 6.1 Agent rail (§3)

- `**GET /api/agents/:hash/metrics`**: per-invocation metric series
(latency, tokens, cost, per-metric scores when present). Current
`/api/agents/:hash` returns only group totals; we need the time
series for the Metrics tab.
- `**GET /api/agents/:hash/parameters`**: parameter values per
invocation, for the Train tab. Walks each invocation's terminal
metadata and reads `parameters[]` (already in metadata).
- `**PATCH /api/runs/:id/notes`**: editable per-run notes column. Keyed
in the SQLite archive store.

### 6.2 Algorithms (§4)

- **TalkerReasoner**: extend `algo_start.payload` to ship the serialized
`ScenarioTree` (id, title, parent_id, terminal, prompt). Trivial; one
line in `talker_reasoner.py:441-452`. Without this the Tree tab can't
draw without a re-fetch.
- **AutoResearcher**: add `attempt_index` to every emitted `iteration`
payload. One line per emit site.
- **AutoResearcher**: emit a `plan` payload (the produced `ResearchPlan`)
after the planner runs, so the Plan tab has data without traversing
synthetic children.
- **OPRO**: it currently emits **no algorithm events**. Add a per-step
`iteration` event with `(value, score, accepted)` so an OPRO view
becomes possible. Without this OPRO is invisible at the algo rail.
- **All algorithms with synthetic children**: ensure `parent_run_id` is
set on inner `agent_event`s. Today this is conditional — verify on
EvoGradient (`evo.py`) and OPRO via `Trainer.fit`. The `Agents` tab
depends on this being right.
- **Trainer**: persist `PromptTraceback.to_jsonl()` to the registry on
each `gradient_applied` so the Traceback tab can pull it.

### 6.3 Metrics as first-class

Right now the only "metrics" we record are latency, tokens, cost. User-
defined `Metric.score()` results never reach the dashboard unless the
caller logs them manually. Promote them:

- The `evaluate(...)` harness already records per-row scores. Extend
`OperadOutput.metadata` to include `metrics: dict[str, float]` when
`evaluate()` invokes the leaf. `serialize_event` already passes
metadata through; `RunInfo.summary()` adds an aggregate `metrics`
field.
- For algorithm-supplied scores (`Beam`, `Sweep`, `Debate`, etc.), the
`algo_emit` payload already carries `score` — just project that to a
per-invocation column on the synthetic children too.

This is the missing link that makes the Metrics tab actually
distinguishable from the Cost tab.

### 6.4 Hash → color stability

Persist the resolved color hue server-side (`RunInfo.color_hue`) so the
sidebar dot, every chart series, and every table swatch agree without
the frontend having to recompute. Defer if needed — `hashColor` is
deterministic, but if we round into the new 12-hue palette in the
frontend, two clients can disagree if the palette changes between
deploys.

### 6.5 Manifest signaling

Extend `/api/manifest` to include `{algorithms: ["Beam","Sweep",...]}`
so the frontend can show empty rails as "no Beam runs yet" rather than
just "empty".

---

## 7. Concrete change list, by file

Frontend:


| Change                                                                          | Files                                                                                                                                                                            |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wire LayoutResolver for `/algorithms/:runId` and `/training/:runId`             | `apps/frontend/src/dashboard/routes.tsx` (add `AlgorithmDetailLayout.tsx`, `TrainingDetailLayout.tsx`); delete the per-algo entries from `runDetailChildren`                     |
| Replace `RunsTable` with one canonical `RunTable` primitive                     | new: `apps/frontend/src/components/ui/run-table.tsx`; delete inline tables in `AgentGroupPage.tsx`, `AgentGroupSubpages.tsx`, `AlgorithmsIndexPage.tsx`, `TrainingIndexPage.tsx` |
| Fix the "single-point series" bug                                               | `AgentGroupPage.tsx::useRunSeries`, `AgentGroupSubpages.tsx::useScatter` — flatten to a single series with N points                                                              |
| Drop `InvocationsBanner` from single-invocation Overview; add slim status strip | `apps/frontend/src/layouts/agent/overview.json` and `OverviewTab.tsx` (single-invocation path)                                                                                   |
| Reduce 4-card "Definition" grid to one collapsible panel with sub-sections      | `apps/frontend/src/layouts/agent/overview.json` (keep group); `OverviewTab.tsx` (single-invocation gets new compact layout)                                                      |
| Add Train tab (rename from Drift); keep Drift only for runs with drift events   | `RunDetailLayout.tsx`, new `TrainTab.tsx` content, `DriftTab.tsx` becomes subordinate                                                                                            |
| Rename Cost → Metrics; rebuild as panel grid (group) and table (single)         | new: `MetricsTab.tsx` for group/single forks; delete `CostTab.tsx`                                                                                                               |
| Build new Tree component for scenario trees                                     | new: `apps/frontend/src/components/algorithms/talker_reasoner/scenario-tree.tsx` and `registry.tsx`; new `talker_reasoner.json` layout                                           |
| Add `Agents` tab to every algorithm layout                                      | each of `beam.json`, `debate.json`, `evogradient.json`, `selfrefine.json`, `sweep.json`, `verifier.json`, `talker_reasoner.json`, `auto_researcher.json` (new)                   |
| Color palette additions                                                         | `apps/frontend/src/styles/tokens.css`                                                                                                                                            |
| `hashColor` rounds to curated palette                                           | `apps/frontend/src/lib/hash-color.ts`                                                                                                                                            |
| Filter / Group by / Sort / New sweep header strip                               | new: `apps/frontend/src/components/panels/section-sidebar/sidebar-toolbar.tsx`; update `section-sidebar.tsx`                                                                     |


Backend (`apps/dashboard/operad_dashboard/`):


| Change                                                                                 | File                                                                                                     |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `GET /api/agents/:hash/metrics`                                                        | new section in `routes/groups.py` (or `agent_routes.py`)                                                 |
| `GET /api/agents/:hash/parameters`                                                     | `agent_routes.py`                                                                                        |
| `PATCH /api/runs/:id/notes`                                                            | new in `runs.py` + persistence layer                                                                     |
| Wire `metrics: dict[str, float]` from `OperadOutput.metadata` into `RunInfo.summary()` | `runs.py:84-112`                                                                                         |
| Trainer: write `PromptTraceback` per `gradient_applied`                                | `routes/gradients.py` (consume), and a small change to `operad/train/trainer.py` to persist the artefact |


Algorithm-side payload deltas (`operad/`):


| Change                                                                                                                              | File:line                                      |
| ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `TalkerReasoner.run()`: add serialized `ScenarioTree` to `algo_start.payload`                                                       | `operad/algorithms/talker_reasoner.py:441-452` |
| `AutoResearcher`: tag every `iteration` with `attempt_index`                                                                        | `operad/algorithms/autoresearch.py:142-189`    |
| `AutoResearcher`: emit `plan` payload after `_one_attempt` planner                                                                  | `operad/algorithms/autoresearch.py:140`        |
| OPRO: emit `iteration` per `_apply_param_update`                                                                                    | `operad/optim/optimizers/opro.py:198-238`      |
| Trainer: add `metrics: dict[str, float]` from per-row metric results to `epoch_end.payload` (already in code paths, just propagate) | `operad/train/trainer.py:460-474`              |


---

## 8. Phasing (each phase shippable on its own)

1. **Phase A — wire the dead layouts.** Cut `runDetailChildren`, route
  `/algorithms/:runId` through `resolveLayout`. Algorithms immediately
   stop looking like agents. (1 day)
2. **Phase B — fix the data bugs.** Single-point series; "Latest
  invocation" eyebrow; AgentFlowGraph single-node fallback. (1 day)
3. **Phase C — rich tables.** New `RunTable` primitive, used by all
  index pages and the agent-group invocations tab. (2 days)
4. **Phase D — Overview redesign.** Slim status strip; single
  collapsible Definition card; preview-then-chevron sections; metrics
   tab as panel grid (group) / table (single). (3 days)
5. **Phase E — Per-algorithm specifics.** Tree (Talker), Lineage
  (Evo), Plan (Researcher), Cells/Heatmap (Sweep) — most of which is
   wiring existing components into the resolved layouts. Add the
   universal "Agents" tab. (3-5 days)
6. **Phase F — Training rail.** Default workspace polish, compare
  mode, optional PromptTraceback tab. (2-3 days)
7. **Phase G — Backend deltas in §6.** Drip them in as needed; not
  blocking on §B/§C/§D.

---

## 9. Things deliberately left out

- **Drag/resize panels.** Adds `react-grid-layout` weight for marginal
visual gain; the static grid + presets approach is enough. Defer.
- **Reports rail.** Months of work, thin payoff. Skip.
- **Server-side workspace persistence.** Local URL + localStorage is
enough until proven otherwise.
- **"Saved 1 minute ago" affordance.** Only meaningful if we have
workspaces to save. Defer.
- **Live "compare" drawer.** Scoped to Phase F; keep `/experiments` as
the destination for now.

---

## 10. Open questions

These should be confirmed before Phase A merges:

1. **Agents tab for algorithms — granularity.** When a Sweep launches
  222 cells and each cell invokes 1 agent, the Agents tab is 222 rows.
   Is that the intent, or do we want grouping by `hash_content` of the
   inner agent (so it collapses into 1 row "Reasoner ×222 invocations
   under this Sweep")? My recommendation: grouped by default, with an
   "ungroup" toggle. This matches the Agents rail's grouping convention.
2. **Metrics tab for the single-invocation page — "delta vs group".**
  Useful but requires loading the group context. Worth the extra
   query, or skip?
3. **Compare drawer vs `/experiments` page.** Keep the existing
  experiments page, build the drawer later, or skip the drawer
   entirely?
4. **Color palette source-of-truth.** Stick with derived hash-hue, or
  adopt a curated 12-hue qualitative palette? Curated is more
   consistent visually but breaks back-compat with already-rendered
   pages.
5. **Notes column.** Free-form Markdown, or structured tag chips?
  Structured tags compose better with the W&B "Tags" column and avoid
   long inline text.
6. **TalkerReasoner Tree visualization.** 2-D static tree (sitemap-
  style) or `@xyflow/react` interactive? Static is simpler and reads
   better for ≤15 nodes; interactive wins for big trees. Default to
   static + a "view as graph" toggle.
7. **OPRO invisibility.** OPRO emits no events today — adding emit is
  straightforward (§6). Is OPRO important enough to merit its own
   per-algorithm view, or do we surface it only as part of a Trainer
   run's gradient log? My take: emit + a minimal "OPRO" view (proposal
   list, accept/reject column, cumulative score), shared with APE/TGD
   structurally.

---

## 11. What this delivers

If we ship Phases A–E:

- Each rail's index is a sortable, dense W&B-style table with sparklines.
- Agent group view tells you, at a glance, how this instance behaves
across invocations — KPIs, latency curve, parameter evolution, drift.
- Single-invocation pages are scannable; you don't drown in 6 redundant
cards before you see the I/O.
- Each algorithm has a view that actually understands its own data.
- The "Agents" tab on every algorithm makes the synthetic-child
topology browsable, jumping users back into the agents rail.
- Color identity is consistent everywhere: sidebar dot, table swatch,
series color, hash chip.
- Training is rich: loss + LR + drift + checkpoints + per-parameter
small multiples + (eventually) a PromptTraceback tab.

The primitives we need (`PanelCard`, `PanelGrid`, `Sparkline`,
`MultiSeriesChart`, `HashTag`, `StatusDot`, `hashColor`,
`AgentFlowGraph`, every chart in `components/charts/`) already exist.
What's missing is composition — and turning the 7 dead-code per-algorithm
JSON layouts back into the source of truth for `/algorithms/:runId`.