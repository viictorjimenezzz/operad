# 03-04 Evolution views: float, categorical, configuration

**Branch**: `dashboard/evolution-numeric`
**Wave**: Sequence 3, parallel batch
**Dependencies**: `01-01` (parameter-evolution endpoint), `01-02`
(density)
**Estimated scope**: medium

## Goal

Build the per-type evolution views for non-text parameters:

- `FloatEvolution` (temperature, top_p, max_tokens) — step plot with
  reference lines for the parameter constraint's default/min/max.
- `CategoricalEvolution` (model, backend, renderer) — state diagram /
  Sankey of distinct values with transitions weighted by run count.
- `ConfigurationEvolution` (whole `Configuration`) — recursive tree;
  each leaf renders the type-appropriate sub-view.

## Why this exists

- §8 of `00-contracts.md` mandates per-type renderers.
- The user said: "Integers like temperature, max tokens... a plot
  would be nice", "Model name: a diagram with the changes".
- §21 inventory lists `FloatParameter`, `CategoricalParameter`,
  `ConfigurationParameter`.

## Files to touch

- New: `apps/frontend/src/components/agent-view/parameter-evolution/float-evolution.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/categorical-evolution.tsx`.
- New: `apps/frontend/src/components/agent-view/parameter-evolution/configuration-evolution.tsx`.
- New: `*.test.tsx` for each.
- Append exports in `parameter-evolution/index.ts` (sibling of brief
  `03-03`'s text views; that brief and this one both edit the same
  index file — additive merge).

## Contract reference

`00-contracts.md` §8 (`ParameterEvolutionPoint`), §3 (palette).

## Implementation steps

### Step 1 — `FloatEvolution`

Step plot using existing `MetricSeriesChart` (or the simpler
`MetricSeriesChart`-based primitive). Y axis = parameter value, X axis
= step index. Step style (no smoothing).

Reference lines (when available from constraint metadata):
- `default` (faint)
- `min` / `max` (dashed grey)

Below the plot, a compact 3-cell stat row:
- min / max / mean over the timeline.

When a step is selected (drawer's `?step`), render a vertical line at
that x and surface the value below the plot in a chip.

### Step 2 — `CategoricalEvolution`

State diagram. Each distinct value is a node positioned roughly
left-to-right by first appearance; transitions are arrows weighted by
the number of consecutive occurrences.

Recommended rendering: a tiny SVG with nodes drawn as colored
rounded rects (color by `paletteIndex(value)`) and edges with a small
counter label. Layout: simple force-free placement on a timeline (x
= first-seen step / total steps).

Below the diagram, render a step-by-step list:
- step 0: "openai/gpt-4o"
- step 1: "openai/gpt-4o-mini"  ← changed from "openai/gpt-4o"
- step 2: "openai/gpt-4o-mini"
- step 3: "anthropic/claude-3-5-sonnet"  ← changed from "openai/gpt-4o-mini"

Click a step → fires `onSelectStep`.

### Step 3 — `ConfigurationEvolution`

Treat the configuration as a tree of dotted paths. For each leaf
sub-path, recursively choose the right view:

- Numeric (e.g. `sampling.temperature`) → mini `FloatEvolution`.
- String (e.g. `model`, `backend`) → `CategoricalEvolution`.
- Boolean (e.g. `io.stream`) → categorical with two states.

Layout: a vertical accordion with each sub-path as a row; expand-
chevron reveals the embedded sub-view.

Tip: the underlying value at each step is a `Configuration` dict;
extract per-path series via dotted-path projection, then call the
appropriate child component.

### Step 4 — Wrapper update

In `parameter-evolution/index.ts` (shared with brief `03-03`), the
`ParameterEvolutionView` switch handles three more types:

```ts
case "float": return <FloatEvolution ... />;
case "categorical": return <CategoricalEvolution ... />;
case "configuration": return <ConfigurationEvolution ... />;
```

## Design alternatives

1. **Float plot: line vs step.** Recommendation: step. Discrete
   training events; a smoothed line over-promises continuity.
2. **Categorical: timeline list vs state diagram.** Recommendation:
   both. The diagram is the headline; the list grounds it. Either
   alone is incomplete.
3. **Configuration: recursive accordion vs flat parameter table.**
   Recommendation: accordion. Configuration trees can be deep;
   flattening hides structure.

## Acceptance criteria

- [ ] `FloatEvolution` renders a step plot; selecting a step
  highlights the corresponding x.
- [ ] `CategoricalEvolution` renders a state diagram with stable
  colors per distinct value; transitions point in the right
  direction.
- [ ] `ConfigurationEvolution` recursively renders the right
  sub-view per dotted path.
- [ ] N=1 graceful rendering for all three.
- [ ] N=0 → `EmptyState`.
- [ ] `pnpm test --run` passes.

## Test plan

- `float-evolution.test.tsx`: 5-step fixture, assert plot renders;
  select a step → callback fires.
- `categorical-evolution.test.tsx`: 4 distinct values across 8 steps,
  assert state diagram has 4 nodes and 3 edges.
- `configuration-evolution.test.tsx`: configuration with sampling +
  io + model; expand each row and assert the right sub-view.

## Out of scope

- The "Why" (gradient) sub-pane (brief `03-05`).
- Text/rules/examples views (brief `03-03`).
- Drawer integration (briefs `03-02`, `04-01`).

## Stretch goals

- `FloatEvolution`: secondary axis showing the gradient severity
  (low/medium/high) as a colored band along the x.
- `CategoricalEvolution`: clicking a state-diagram node filters the
  step list to occurrences of that value.
- `ConfigurationEvolution`: highlight rows where the value changed
  during the timeline, dim the rest.
