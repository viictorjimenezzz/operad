# 03-03 Evolution views: text, rules, examples

**Branch**: `dashboard/evolution-text`
**Wave**: Sequence 3, parallel batch
**Dependencies**: `01-01` (parameter-evolution endpoint), `01-02`
(density)
**Estimated scope**: medium

## Goal

Build the per-type evolution views for text-shaped parameters:

- `TextParameter` (role, task) — vertical timeline of versions with
  diff between adjacent steps and expand-for-full-text.
- `RuleListParameter` (rules) — lifelines: per-rule rows × per-step
  columns; cells colored when the rule existed at that step,
  struck-through when removed.
- `ExampleListParameter` (examples) — same lifeline pattern, but each
  cell expands to show the (input, output) pair.

These three are the "text gravity" of the parameter-evolution
experience and they share patterns; one brief covers them.

## Why this exists

- §8 of `00-contracts.md` defines the data shape; per-type renderers
  are mandated by the user's spec.
- The user said: "Prompts: a diff preview with a chevron to expand
  and see the whole prompt would be nice."
- §21 of the inventory exposes `RuleListParameter` and
  `ExampleListParameter`; they deserve dedicated views, not a generic
  fallback.

## Files to touch

- New: `apps/frontend/src/components/agent-view/parameter-evolution/text-evolution.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/rule-list-evolution.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/example-list-evolution.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/index.ts` —
  re-export.
- New: `*.test.tsx` for each.
- May import from `apps/frontend/src/components/charts/multi-prompt-diff.tsx`
  (existing) for the diff rendering.

## Contract reference

`00-contracts.md` §8 (`ParameterEvolutionPoint`), §3 (palette).

## Implementation steps

### Step 1 — `TextEvolution`

Props:
```ts
export interface TextEvolutionProps {
  points: ParameterEvolutionPoint[];       // value: string
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
}
```

Layout: vertical timeline. Each step is a row:

```
┌─ step #N ──────────────────────────── runId · 5m ago · langfuse →
│  hash abcdef…                         severity: medium
│  ┌─ diff vs step #N-1 ───────────────────────────────────────┐
│  │ - You decompose research questions into 3 sub-questions.  │
│  │ + You decompose a research question into three            │
│  │ + independent sub-questions: biology, policy, economic.   │
│  └────────────────────────────────────────────────────────────┘
│  ▾ expand to see full text (markdown)
└────────────────────────────────────────────────────────────────
```

- Diff: reuse `MultiPromptDiff` (`charts/multi-prompt-diff.tsx`) or
  inline a simple word-diff. Recommendation: reuse, with a small
  wrapper for adjacency.
- Expand-chevron uses `<details>` with markdown rendered by
  `MarkdownView`.
- The selected step gets a tinted background and is scrolled into
  view on selection change.
- No diff for step 0 (initial value).

### Step 2 — `RuleListEvolution`

Treat each rule as a "row" identified by its content hash. Each
column is a step.

```
                  step 0   step 1   step 2   step 3   step 4
"Be concise."     ████     ████     ████     ████     ────
"Always cite."                      ████     ████     ████
"Use English."    ████     ────     ────     ────     ────
"Avoid emoji."             ████     ████     ████     ████
```

- Cell shaded with the row's rule-hash color when the rule was
  present at that step; thin line when absent.
- Hover a cell → tooltip with the rule text (full).
- Click a cell → selects that step (calls `onSelectStep`).
- Below the grid, when a step is selected, render the full rule list
  for that step in numbered order with new rules highlighted green
  and removed rules struck-through grey.

### Step 3 — `ExampleListEvolution`

Same lifeline pattern as rules but each cell, when clicked, opens an
inline expansion below showing the (input, output) pair as
side-by-side `FieldTree` blocks.

### Step 4 — Common wrapper

```tsx
export function ParameterEvolutionView({ type, points, ... }: ...) {
  switch (type) {
    case "text": return <TextEvolution ... />;
    case "rule_list": return <RuleListEvolution ... />;
    case "example_list": return <ExampleListEvolution ... />;
    default: return null;
  }
}
```

Brief `04-01` consumes this via the drawer's children prop.

## Design alternatives

1. **Diff rendering: `MultiPromptDiff` vs a fresh inline diff.**
   Recommendation: reuse — already battle-tested, has tests.
2. **Rules/examples as lifelines vs as a per-step list.**
   Recommendation: lifelines. The user wants to see _which_ rules
   changed at each step, not just "the rules at this step".
3. **One row per distinct rule-hash vs one row per rule slot index.**
   Recommendation: per-hash. A reorder-without-edit shouldn't show
   as two rows changing; it should preserve identity.

## Acceptance criteria

- [ ] TextEvolution renders an N-step timeline; the selected step has
  a tinted background; expand-chevron shows the full text.
- [ ] RuleListEvolution shows one row per distinct rule (across all
  steps), with cells colored when the rule was present.
- [ ] ExampleListEvolution renders the lifeline grid; clicking a cell
  expands the (input, output) inline.
- [ ] When `points.length === 1`, all three views render gracefully
  (no diff, just the single value).
- [ ] When `points.length === 0`, render an `EmptyState` with the
  shape "no observed values yet".
- [ ] `pnpm test --run` passes.

## Test plan

- `text-evolution.test.tsx`: 3-step fixture; assert diff between
  steps 0→1; click step 2 → callback fires.
- `rule-list-evolution.test.tsx`: 4 distinct rules across 5 steps;
  assert lifeline cell presence/absence.
- `example-list-evolution.test.tsx`: similar.

## Out of scope

- The "Why" (gradient) sub-pane (brief `03-05`).
- Numeric / categorical / configuration views (brief `03-04`).
- Drawer integration (briefs `03-02`, `04-01`).

## Stretch goals

- TextEvolution: render a tiny scrollable "minimap" on the right
  edge showing each step as a 4px-tall sliver, color-coded by
  severity.
- RuleListEvolution: stable color per rule-hash so the same rule
  keeps the same color across the whole timeline (already the spec
  with `hashColor(rule_hash)`).
- ExampleListEvolution: a `?expand=all` URL flag that opens every
  cell at once for high-density review.
