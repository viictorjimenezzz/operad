# 02-02 Group Overview and Metrics — N-aware rendering

**Branch**: `dashboard/group-overview-and-metrics`
**Wave**: Sequence 2, parallel batch
**Dependencies**: `01-02` (HashRow, density tokens, conditional cell
kinds)
**Estimated scope**: medium

## Goal

Make the agent-group Overview and Metrics tabs N-aware: don't render
1-point line charts; don't show "Recent runs" since the Invocations
tab exists; promote the activity strip to the top; let the
single-invocation case look like a real instance page rather than a
stub.

## Why this exists

- `AgentGroupOverviewTab.tsx` currently shows a `Latency × invocation`
chart that is meaningless when N=1 (single point). The user
explicitly called this out.
- The "Recent runs" panel duplicates the Invocations tab; the user
wants it removed.
- `AgentGroupMetricsTab.tsx` always renders 6 `MetricSeriesChart`
panels regardless of N; flat lines for N=1 are noise.

## Files to touch

- `apps/frontend/src/dashboard/pages/AgentGroupOverviewTab.tsx` —
reorder + conditional rendering.
- `apps/frontend/src/dashboard/pages/AgentGroupMetricsTab.tsx` —
N-aware rendering.
- `apps/frontend/src/components/agent-view/group/identity-card.tsx` —
flatten the bordered card into a borderless block.

## Contract reference

`00-contracts.md` §3 (palette), §4 (density), §1 (identity).

## Implementation steps

### Step 1 — Group Overview reorder

Order from top to bottom:

1. **Identity block** (re-skinned `AgentGroupIdentityCard`) — class
  name, root path, `hash_content` chip, trainable count.
2. **Activity strip** — borderless metrics bar:
  `runs · ok% · p50 latency · tokens · cost · live count`.
3. **N≥2 only**: a single `MultiSeriesChart` overlaying
  `latency`, `cost`, and `tokens` per invocation, each its own color
   line. Toggle strip lets the user pick which to show. Min height
   220px.
4. **N=1 only**: a 2-column `Definition + Reproducibility` view
  identical in shape to `02-01`'s single-invocation Overview, scoped
   to the only invocation. (Reuse the components from `02-01`.)

Drop:

- The "Recent runs" `PanelSection` (lines 66-82).
- The standalone `Latency × invocation` chart (lines 55-65).

### Step 2 — `IdentityCard` flattening

Drop the `rounded-lg border bg-bg-1 px-4 py-3` wrapper. Render as a
borderless block separated from the Activity strip by a thin
`border-b border-border`. Keep the hash chip on the right.

### Step 3 — Metrics tab N-awareness

```ts
const N = runs.length;

if (N === 1) renderMetricTable(runs);
else if (N <= 4) renderMiniBars(runs);
else renderSeries(runs);
```

- `renderMetricTable` — one row per metric, columns `metric · value · unit`. Use `RunTable` with the new `score` cell (brief `01-02`)
for the value when bounded; plain `text` otherwise.
- `renderMiniBars` — for each metric, render N tiny horizontal bars
side by side, each labeled by `run_id`'s short form. No axes.
- `renderSeries` — keep the existing `MetricSeriesChart` panels but
filter out metrics with fewer than 2 distinct values
(e.g. `schema_validation_rate=1` over 10 runs is noise).

Drop the `Cost vs latency` and `Tokens vs latency` `PanelGrid` when
N=1; keep when N≥2.

### Step 4 — Metric source labels

For each metric, label its source: `built-in` (latency_ms,
prompt_tokens, completion_tokens, cost_usd) vs
`<agent_path>` (user-emitted via `OperadOutput.metadata["metrics"]`).
Render the source as an `Eyebrow` above each metric block. This makes
it obvious which metric is "free" vs "your code emits this".

## Design alternatives

1. **N=1 Overview shows the single invocation in full vs a placeholder
  "see Invocations".** Recommendation: show in full. The user said
   "should be one parent entry with one child" — when the user lands
   on the parent, they should see the child's content, not a redirect
   prompt.
2. **N≥5 series chart: one panel per metric vs one big overlay.**
  Recommendation: one panel per metric (existing); overlay only when
   the user explicitly toggles "compare metrics".
3. **Mini-bars at N=2-4 vs always render the series chart.**
  Recommendation: mini-bars. Two-point line plots look fragile.

## Acceptance criteria

- On a single-invocation group (example 01), Overview renders the
Identity + Activity + Definition + Reproducibility shape, not a
1-point chart and not a "Recent runs" duplicate.
- On a multi-invocation group (≥2), Overview renders the unified
`MultiSeriesChart` with metric toggles.
- Metrics tab on N=1 renders a metric table; on N=2-4 renders
mini-bars; on N≥5 renders the existing series panels.
- Each metric panel has an `Eyebrow` indicating source
(`built-in` or `<agent_path>`).
- No bordered card wrapping inside identity/activity blocks.
- `pnpm test --run` passes.

## Test plan

- New `agent-group-overview-tab.test.tsx`: render with N=1 fixture and
assert no `Latency × invocation` panel; render with N=3 and assert
presence.
- New `agent-group-metrics-tab.test.tsx`: render with N=1, N=3, N=8
fixtures and assert the right rendering branch.
- Manual: example 01 (N=1), examples with multiple invocations
(synthesize via re-runs).

## Out of scope

- Training tab (brief `02-04`).
- Algorithm pages (Sequence 5).
- Parameter evolution (Sequence 3).

## Stretch goals

- Add a "drift since first invocation" indicator to the Identity
block: number of hash deltas across invocations, color-coded.
- Add a hover-preview popover on each metric mini-bar showing the
full run id and the value.
- The N≥5 series chart adds an "outlier toggle" that highlights runs
with z-score > 2.

