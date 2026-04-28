# 03-05 Evolution "Why" sub-pane

**Branch**: `dashboard/evolution-why-pane`
**Wave**: Sequence 3, parallel batch
**Dependencies**: `01-01` (parameter-evolution endpoint with
`gradient` and `tape_link`)
**Estimated scope**: small

## Goal

When a user selects a step in any of the per-type evolution views,
the drawer body splits into two regions: top = the per-type view
(builds 03-03 / 03-04 own this), bottom = the "Why" pane (this
brief). "Why" surfaces the `TextualGradient` that produced the
selected step plus the optimizer/critic context.

## Why this exists

- §8 of `00-contracts.md` defines `gradient` and `sourceTapeStep` on
  `ParameterEvolutionPoint`; without surfacing them the data is
  inert.
- §21 of the inventory is the entire training story; the gradient is
  the operad-specific signal that distinguishes our dashboard.
- The user explicitly said: "click on a specific state, I can see the
  value but also the 'gradient' that generated it and any other
  metrics associated to training".

## Files to touch

- New: `apps/frontend/src/components/agent-view/parameter-evolution/why-pane.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/why-pane.test.tsx`.
- Append re-export in
  `apps/frontend/src/components/agent-view/parameter-evolution/index.ts`.

## Contract reference

`00-contracts.md` §8 (`TextualGradient`, `TapeStepRef`,
`ParameterEvolutionPoint`).

## Implementation steps

### Step 1 — Component

```tsx
export interface WhyPaneProps {
  point: ParameterEvolutionPoint | null;
  previous?: ParameterEvolutionPoint | null;   // for context
  langfuseUrl?: string | null;                  // base URL from manifest
}

export function WhyPane({ point, previous, langfuseUrl }: WhyPaneProps) {
  if (!point) return <EmptyState title="select a step" description="..." />;
  return (
    <div className="border-t border-border p-3 space-y-3">
      <Header point={point} />
      {point.gradient ? <GradientCard gradient={point.gradient} /> : null}
      {point.sourceTapeStep ? <TapeStepCard step={point.sourceTapeStep} /> : null}
      {point.metricSnapshot ? <MetricsRow metrics={point.metricSnapshot} /> : null}
      <Footer point={point} previous={previous} langfuseUrl={langfuseUrl} />
    </div>
  );
}
```

Sections rendered (top to bottom, all optional):

1. **Header** — `step #N · runId · started X ago · langfuse →`.
2. **GradientCard** — the textual gradient. Markdown-rendered
   `message`. `severity` chip (`low/medium/high` with
   `--color-ok/warn/err`). `target_paths` as a chip strip.
3. **TapeStepCard** — `epoch N · batch N · iter N · optimizer step N`
   in a 4-cell `Metric` row.
4. **MetricsRow** — `{train_loss, val_loss, lr, accuracy, …}` as a
   horizontal `Metric` strip.
5. **Footer** — `delta vs previous step`: hash diff, value diff
   (numeric or count of changed words for text), latency delta if
   available.

### Step 2 — Critic deep-link

When `point.gradient.critic.langfuseUrl` is present, expose a
`Open critic invocation in Langfuse →` link. This is the single
deepest piece of provenance: "the gradient that mutated this
parameter was produced by THIS specific critic invocation".

### Step 3 — Empty states

- `point == null` → "Select a step in the timeline above to see how it
  changed."
- `point.gradient == null` → "This step's value was set without a
  textual-gradient critic (e.g. initial value or hand-edit)."

## Design alternatives

1. **Inline the WhyPane below the per-type view vs side-by-side.**
   Recommendation: inline below. The drawer width clamps at 720px;
   side-by-side cramps both.
2. **Render the gradient `message` as plain text vs markdown.**
   Recommendation: markdown — `MarkdownView` is already used; the
   message often contains lists.
3. **Always render the WhyPane vs only when a step is selected.**
   Recommendation: always render; show empty state when no step.
   Continuous presence reduces UI flicker.

## Acceptance criteria

- [ ] When a step has a gradient, the message renders as markdown,
  severity chip is colored, target_paths render as chips.
- [ ] When a step has a `sourceTapeStep`, the 4-cell Metric row
  renders epoch/batch/iter/optimizer_step.
- [ ] When a step has `metricSnapshot`, those metrics render in a
  horizontal strip.
- [ ] When a step has a `critic.langfuseUrl`, the deep-link is
  visible.
- [ ] When no step is selected, the empty state renders.
- [ ] When a step has no gradient (initial value / hand-edit), the
  appropriate empty state renders without crashing.
- [ ] `pnpm test --run` passes.

## Test plan

- `why-pane.test.tsx`: render with full fixture (gradient + tape +
  metrics) → all sections present. Render with `point=null` → empty
  state. Render with `gradient=null` → "no gradient" hint.

## Out of scope

- Wiring the WhyPane into the drawer (brief `04-01`).
- Backend emit of gradient context (brief `01-01`).

## Stretch goals

- "Step into the critic" affordance: clicking the critic deep-link
  opens the critic's invocation in a separate side-by-side mini
  drawer (this is operad's `gdb` story).
- Add a "diff vs current" mode: show how this historical value
  differs from the latest, not just from the previous step.
- Show a tiny inline cost/latency bar for the gradient_applied step
  (cost of the critic invocation that produced the gradient).
