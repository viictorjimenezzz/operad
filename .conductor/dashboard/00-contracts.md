# 00 — Shared contracts

This is the single source of truth for the redesign. Every shared decision
(palette, density, JSON layout types, backend route shapes, navigation
URLs, component props with cross-cutting use) lives here. If your brief
disagrees with this file, post a clarification question and stop.

Sections are stable identifiers — refer to them as `§N` in PR bodies.

---

## §1 Identity model (navigation)

The dashboard exposes three identity levels for agents:

| Level | Source | Display |
|---|---|---|
| **Class** | dotted `root_agent_path` (last segment) | `research_analyst`, `Reasoner`, `Trainer` |
| **Instance** | `hash_content` of the root agent at run time | colored swatch + `hash_content[:10]` |
| **Invocation** | `run_id` | mono short id |

Algorithms expose two identity levels:

| Level | Source | Display |
|---|---|---|
| **Class** | `algorithm_class` (last segment of `algorithm_path`) | `Sweep`, `Beam`, `Trainer` |
| **Invocation** | `run_id` | one row per invocation; class is the row's primary label |

Both rails are *always three-level* in the sidebar (or two-level for
algorithms): no collapse-on-singleton. The user explicitly chose this in
the design discussion.

URL conventions (`apps/frontend/src/dashboard/routes.tsx`):

```
/agents                                 — list of classes (NEW)
/agents/_class_/<className>             — list of instances of one class (NEW; URL-encode)
/agents/<hashContent>                   — instance overview (existing)
/agents/<hashContent>/{runs,metrics,training,graph}
/agents/<hashContent>/runs/<runId>      — invocation (existing)
/algorithms                             — list of classes
/algorithms/<runId>                     — invocation (existing)
/training/<runId>                       — invocation (existing)
```

The new class-level page lives under
`apps/frontend/src/dashboard/pages/AgentsByClassPage.tsx`. It enumerates
the instances of one class with a class-tinted rail. See `01-03`.

---

## §2 The "Train" tab gate

`AgentGroupPage.tsx` decides whether the "Training" tab is visible. The
correct gate is:

```ts
const showTraining =
  detail.is_trainer ||
  (meta.data?.trainable_paths.length ?? 0) > 0;
```

The previous extra clause `detail.runs.some(run => run.metrics?.best_score != null)`
must be removed. `best_score` is propagated by *any* algorithm; it does
not imply the agent has trainable parameters.

The tab label is `"Training"` (not `"Train"`).

---

## §3 Color palette

### Per-instance (identity)

```ts
import { hashColor, hashColorDim, hashColorGlow, paletteIndex } from "@/lib/hash-color";

hashColor(hashContent)        // var(--qual-N), N=1..12 by hash fold
hashColorDim(hashContent, a)  // color-mix transparent
hashColorGlow(hashContent)    // dim with α=0.55 for ambient borders
```

Use `hashColor(identity)` for:
- Sidebar dots (when grouping by instance)
- Table left-rail (`RunTable._color`)
- Chart series (`MetricSeriesChart`, `MultiSeriesChart`)
- Drawer header rails (4-6px left bar)

### Per-class (categorical)

For sidebar dots when the row IS a class (algorithm class header,
agent-class header in the new index page), use:

```ts
const color = `var(--qual-${paletteIndex(className) + 1})`;
```

This makes `Sweep` and `Beam` and `Trainer` consistently distinct
across screens.

### When neither applies

Use `--color-accent` for default emphasis. Never invent ad-hoc hex
values. If you need an additional palette token, propose it in your PR
body — do not silently add to `tokens.css`.

---

## §4 Density tokens (extension to `tokens.css`)

Add the following to `@theme` in
`apps/frontend/src/styles/tokens.css`:

```css
--row-h: 28px;             /* table rows, sidebar rows */
--row-h-tight: 22px;       /* tape entries, log lines, dense lists */
--panel-pad-y: 8px;        /* was de-facto 12px */
--panel-pad-x: 12px;
--canvas-gutter: 1px;      /* divider rule between sections */
--drawer-width: 50vw;      /* parameter drawer; clamps to [480px, 720px] */
--drawer-min: 480px;
--drawer-max: 720px;
```

Existing `--row-height-sm: 28px` and `--row-height-xs: 22px` are kept
(used by `RunTable`); new tokens are additive.

The "no bordered card per inner element" rule: replace
`rounded-lg border bg-bg-1 px-3 py-2` wrappers around inner content
with `border-b border-border` dividers and inline padding. The outer
page section may still use the bordered card; nested ones must not.

---

## §5 `RunTable` cell kinds

Existing kinds in `apps/frontend/src/components/ui/run-table.tsx` are
kept: `text · num · pill · hash · sparkline · link · markdown`.

Add:

```ts
| { kind: "param"; value: unknown; previous?: unknown; format?: "auto" | "text" | "number" }
| { kind: "score"; value: number | null; min?: number; max?: number }
| { kind: "diff"; value: string; previous?: string }
| { kind: "image"; src: string; alt: string; width?: number; height?: number }
```

Renderers:
- `param` — value formatted by inferred type; if `previous` present and
  differs, render with arrow + delta in muted color.
- `score` — value + thin horizontal bar normalized to `[min, max]`,
  colored by sign or by `--color-ok/--color-warn/--color-err` based on
  bands.
- `diff` — string with red/green inline highlight; truncated to
  ~80ch with hover-expand.
- `image` — small img/svg; used for categorical change-diagram
  thumbnails and tape sparklines.

Renderer extensions live in `run-table.tsx` itself; do not branch.

---

## §6 `HashRow` primitive (NEW)

Single row of 7 hash chips for the operad reproducibility fingerprint.

```ts
// apps/frontend/src/components/ui/hash-row.tsx
export interface HashRowProps {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
  size?: "sm" | "md";
  onCopy?: (key: HashKey, value: string) => void;
}

export type HashKey =
  | "hash_model"
  | "hash_prompt"
  | "hash_input"
  | "hash_output_schema"
  | "hash_config"
  | "hash_graph"
  | "hash_content";
```

Behavior:
- Each chip: 12-char monogram + tiny color dot from `hashColor(value)`.
- Hover → tooltip with the full hex (copyable).
- When `previous` is provided and `previous[key] !== current[key]`,
  render the chip with `--color-warn` outline + a tiny diff indicator.

Owned by brief `01-02`. All other briefs consume.

---

## §7 `StructureTreeNode` shape

The agent's structural tree (used by Training, Graph context, and the
parameter drawer source).

```ts
// apps/frontend/src/lib/structure-tree.ts
export type StructureTreeNode = {
  path: string;                    // e.g. "research_analyst.stage_1.biology_branch.stage_0"
  label: string;                   // e.g. "biology_branch" or "Reasoner" (last segment)
  className: string;               // runtime class name, e.g. "Reasoner"
  kind: "composite" | "leaf";
  hashContent: string | null;      // resolved at runtime; null until first invocation
  children: StructureTreeNode[];   // composite branches; empty for leaves
  parameters: ParameterDescriptor[];
};

export type ParameterDescriptor = {
  path: string;                    // dotted, relative to the agent (e.g. "role")
  fullPath: string;                // structureTreeNode.path + "." + path
  type: "text" | "rule_list" | "example_list" | "float" | "categorical" | "configuration";
  requiresGrad: boolean;
  currentValue: unknown;
  currentHash: string;
};
```

The tree is built client-side from:
- `/api/agents/{hash}/runs[].graph_json` (the AgentGraph snapshot)
- `/runs/{id}/agent/{path}/parameters` (per-leaf parameters API)

Default expansion (per user's choice in the design discussion): collapse
composites with >5 children; expand the rest. Leaves are always
collapsed; clicking expands to show their `parameters`.

---

## §8 Parameter evolution data model

For the per-parameter timeline view:

```ts
export type ParameterEvolutionPoint = {
  runId: string;                   // the invocation that set this value
  startedAt: number;               // epoch seconds
  value: unknown;                  // raw value at this step
  hash: string;                    // stable short hash of `value`
  gradient?: TextualGradient;      // present when produced by a Trainer step
  sourceTapeStep?: TapeStepRef;    // back-reference into the tape
  langfuseUrl?: string | null;
  metricSnapshot?: Record<string, number>;  // e.g. {"train_loss": 0.71}
};

export type TextualGradient = {
  message: string;                 // markdown-renderable
  severity: "low" | "medium" | "high";
  targetPaths: string[];           // dotted paths inside the agent
  critic?: { agentPath: string; runId: string; langfuseUrl?: string | null };
};

export type TapeStepRef = {
  epoch: number;
  batch: number;
  iter: number;
  optimizerStep: number;
};
```

The frontend reads this from a NEW endpoint (see §10):
`GET /runs/{run_id}/parameter-evolution/{path:path}`.

Per-type views map to these fields differently:
- `text` (role, task) → `message`, `value` rendered as markdown diff
- `rule_list` → diff per element
- `example_list` → diff per item, expand for full I/O
- `float` → step plot of `value`
- `categorical` → state-diagram of distinct values
- `configuration` → tree of dotted paths, each leaf a recursive view

---

## §9 Drawer URL state

The parameter drawer is URL-controlled so users can share a link:

```
/agents/<hashContent>/training?param=<dotted.full.path>&step=<index>
/algorithms/<runId>?tab=parameters&param=<dotted.full.path>&step=<index>
```

Behavior:
- `?param` opens the drawer; absence closes it.
- `?step` selects a step in the timeline; defaults to last.
- Escape key closes the drawer (clears `?param` and `?step`).
- Closing via the X button does the same.
- Browser back/forward navigate through drawer states.

Drawer width is `clamp(--drawer-min, --drawer-width, --drawer-max)`.

---

## §10 Backend routes

### Existing (kept)

- `GET /runs` — `RunSummary[]`
- `GET /runs/{id}/summary` — `RunSummary`
- `GET /runs/{id}/events?limit=N`
- `GET /runs/{id}/children` — synthetic children
- `GET /graph/{id}` — `{mermaid: string}`
- `GET /runs/{id}/agent/{path:path}/{meta,invocations,prompts,events,parameters,diff}`
- `GET /runs/{id}/{fitness,mutations,drift,progress,sweep}.{json,sse}`
- `GET /api/agents`, `/api/agents/{hash}`, `/api/agents/{hash}/{runs,metrics,parameters}`
- `GET /api/algorithms`, `/api/trainings`, `/api/opro`
- `GET /api/manifest` — `{mode, version, langfuseUrl, allowExperiment, cassetteMode}`

### Modified

- `GET /api/agents` — additionally returns `class_name` (already does).
  No shape change; add a top-level `/api/agent-classes` that buckets the
  same data by `class_name` (see brief `01-01`).
- `GET /api/manifest` — adds `cassettePath`, `cassetteStale`, `tracePath`.
- `GET /runs/{id}/agent/{path:path}/parameters` — per-param entry adds
  `tape_link?: TapeStepRef` and `gradient?: TextualGradient` when the
  param was produced by an optimizer step.

### NEW

- `GET /api/agent-classes` →
  `Array<{ class_name, root_agent_path, instance_count, last_seen, first_seen, instances: AgentGroupSummary[] }>`
- `GET /runs/{run_id}/parameter-evolution/{path:path}` →
  `{ path, type, points: ParameterEvolutionPoint[] }`. The implementation
  joins per-leaf parameter snapshots from `RunInfo.parameter_snapshots`
  with `gradient_applied` algo events by timestamp.

---

## §11 JSON layout element types (per-algorithm)

Layouts under `apps/frontend/src/layouts/*.json` are loaded via
`import.meta.glob`. The element registry resolves type strings to React
components via `apps/frontend/src/components/runtime/dashboard-renderer.tsx`.

Reserved universal element types:

```
Tabs                       Top-level tab strip with badges
PanelCard                  Sectioned card with title/eyebrow
PanelGrid                  Responsive grid container
EmptyState                 Empty-state primitive
EventsTab                  Universal event log (already exists)
AgentsTab                  Universal child-runs table (already exists)
InvocationsTab             NEW — per-algorithm rich invocations table
ParametersTab              NEW — StructureTree + drawer for parameter evolution
HashRow                    NEW — reproducibility chip row
```

Reserved per-algorithm element types (one per family):

```
SweepDetailOverview · SweepHeatmapTab · SweepCellsTab · SweepCostTab
                                       · SweepParallelCoordsTab (NEW)
BeamLeaderboardTab · BeamCandidatesTab · BeamHistogramTab
DebateRoundsTab · DebateTranscriptTab · DebateConsensusTab
EvoLineageTab · EvoPopulationTab · EvoOperatorsTab
TrainerLossTab · TrainerScheduleTab · TrainerDriftTab · TrainerTracebackTab
OPROPromptHistoryTab · OPROScoreCurveTab
SelfRefineLadderTab · SelfRefineIterationsTab
AutoResearcherPlanTab · AutoResearcherAttemptsTab · AutoResearcherBestTab
TalkerTreeTab · TalkerTranscriptTab · TalkerDecisionsTab
VerifierIterationsTab · VerifierAcceptanceTab
```

Each per-algorithm component lives under
`apps/frontend/src/components/algorithms/<algo>/<TabName>.tsx` and is
registered by adding a single line to
`apps/frontend/src/components/algorithms/registry.tsx`. Two briefs
both editing `registry.tsx` is the only shared-territory edit allowed
in Sequence 5; conflicts are merge-trivial because each brief adds
disjoint imports.

---

## §12 Per-algorithm breadcrumb KPIs

`AlgorithmDetailLayout.tsx` renders trailing KPIs in the breadcrumb. The
per-class additions (computed from existing `RunSummary` fields):

| Class | KPIs (label / source) |
|---|---|
| `Sweep` | `cells / generations.length`, `best / max(metrics.score)` |
| `Beam` | `K / candidates.length`, `top / max(candidates.score)` |
| `Debate` | `rounds / rounds.length`, `consensus / last(rounds.scores).std` |
| `EvoGradient` | `gens / generations.length`, `pop / generations[0].scores.length`, `best / max(generations.best)` |
| `Trainer` | `epochs / max(iterations.epoch)`, `best_val / min(metrics.val_loss)`, `lr / last(LRLogger).lr` |
| `OPRO` | `iters / iterations.length`, `best / algorithm_terminal_score` |
| `SelfRefine` | `iters / iterations.length`, `best / algorithm_terminal_score` |
| `AutoResearcher` | `attempts / iterations.filter(plan).length`, `best / algorithm_terminal_score` |
| `TalkerReasoner` | `turns / iterations.length` |
| `Verifier` | `iters / iterations.length`, `acc / iterations.filter(accepted).length / iters` |

The mapping is owned by brief `02-05`; subsequent briefs may extend it
when they discover additional summary fields.

---

## §13 Component registry conventions

```
apps/frontend/src/components/
  ui/                       # generic, no operad knowledge
  charts/                   # generic chart primitives (existing)
  panels/                   # global rail, stats, sidebar (existing)
  agent-view/               # agent rail-specific
    overview/               # single-invocation tabs
    group/                  # group page tabs
    graph/                  # graph + inspector
    page-shell/             # chrome
    structure/              # StructureTree, drawer (NEW; brief 03-01, 03-02)
    parameter-evolution/    # per-type evolution views (NEW; briefs 03-03..05)
  algorithms/               # algorithm rail-specific
    <algo>/                 # one folder per class
    registry.tsx            # additive imports only
  runtime/
    dashboard-renderer.tsx  # element-type → React component map (additive)
```

Registries are append-only. Two parallel briefs editing `registry.tsx`
add disjoint lines and merge cleanly.

---

## §14 Monitor-only invariant

The dashboard renders. It does not mutate. Specifically:

- **Delete** `apps/frontend/src/components/agent-view/graph/inspector/tab-experiment.tsx`
  and the "Edit & run" inspector tab.
- **Delete** the "Replay" and "Cassette replay" buttons in
  `apps/frontend/src/components/agent-view/overview/io-hero.tsx`.
- **Delete** any code path that calls `dashboardApi.agentInvoke(...)`.
- **Delete** the `tab-agent-langfuse.tsx` inspector tab (Langfuse is now
  surfaced as an inline link in Overview).

Manifest fields `allowExperiment` and `cassetteMode` remain in the API
surface but the SPA does not read `allowExperiment` after this redesign.
The backend retains `agent_invoke` for testing harnesses; the SPA does
not call it.

---

## §15 Data emission requirements (operad core, not dashboard)

These are the assumptions the dashboard makes about what the operad
core emits. If a brief discovers a gap, it must surface it in the PR
body and a follow-up issue under `operad/runtime/` — not paper over it
in the frontend.

- `OperadOutput.metadata.parameters: list` — present on every leaf
  agent's `end` event, contains `requires_grad`, `path`, `value`,
  `hash`, and (from this redesign onward) optional `gradient` and
  `tape_link`.
- `algo_event` of kind `gradient_applied` — emitted by every optimizer
  step with `target_paths`, `severity`, `message`, `epoch`, `batch`,
  `iter`, `optimizer_step`.
- `algo_event` of kind `iteration` (Trainer) — emits
  `parameter_snapshot` at `phase=epoch_end`.
- `RunInfo.traceback_path` — set when `PromptTraceback.save()` is
  called; consumed by `TrainerTracebackTab`.
- `metadata.metrics: dict` — propagated into `RunInfo.metrics` (already
  works, see `runs.py:574-583`).

If any of the above is not present on a live run, the relevant tab
shows an `EmptyState` with the specific shape required, not generic
"no data".

---

## §16 Test conventions

- Frontend unit tests: `vitest` + `@testing-library/react`. Each new
  component ships at least one render test that asserts on a
  user-visible string + one interaction test where applicable.
- Backend route tests: `pytest` with the existing `client` fixture in
  `apps/dashboard/tests/conftest.py`.
- Cross-browser snapshot tests: not required.
- Layout JSON validation: `apps/frontend/src/layouts/LayoutResolver.test.ts`
  parses every JSON; new tabs must keep that test passing.

---

## §17 Out-of-scope for this redesign

- Mobile / narrow-viewport responsiveness.
- Multi-user collaboration / auth / persistent storage beyond replay.
- New `Configuration` backends or model wrappers.
- Anything inside `operad/` that isn't an emit-site fix flagged by §15.

When in doubt, mention it in the PR body — do not silently expand scope.
