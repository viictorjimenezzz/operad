# 04-01 Training tab integration

**Branch**: `dashboard/training-tab-integration`
**Wave**: Sequence 4 (single task)
**Dependencies**: `01-01`, `01-02`, `01-03`, `02-04`, `03-01`,
`03-02`, `03-03`, `03-04`, `03-05`
**Estimated scope**: medium

## Goal

Wire the `StructureTree` + `ParameterDrawer` + per-type evolution
views (built in Sequence 3) into:

1. The agent-group **Training** tab (`AgentGroupTrainTab.tsx`).
2. A new **Parameters** tab on each mutating algorithm's detail page
   (Trainer, EvoGradient, OPRO, SelfRefine, APE, MomentumTextGrad,
   TextualGradientDescent — plus any future class registered as
   "mutating"). The tab is universal but driven by per-run data.

This brief is the keystone: when it merges, the user can click a
trainable parameter from any agent in any rail and see its full
evolution timeline with gradient context.

## Why this exists

The user explicitly said: "this story should also live inside the
algorithm view, because the algorithm is the thing making the
changes". §11 of `00-contracts.md` reserves the `ParametersTab`
universal element type.

## Files to touch

- `apps/frontend/src/dashboard/pages/AgentGroupTrainTab.tsx` —
  rebuild around StructureTree + Drawer.
- `apps/frontend/src/components/agent-view/parameter-evolution/parameters-tab.tsx` —
  new: the universal element, used by JSON layouts.
- `apps/frontend/src/components/runtime/dashboard-renderer.tsx` —
  register `ParametersTab` element type.
- All mutating algorithm JSON layouts:
  `apps/frontend/src/layouts/{trainer,evogradient,opro,selfrefine}.json` —
  add a `parameters` tab with element type `ParametersTab`.
- `apps/frontend/src/components/agent-view/parameter-evolution/parameters-tab.test.tsx` —
  new test.
- `apps/frontend/src/components/agent-view/structure/index.ts` —
  ensure exports are complete.

## Contract reference

`00-contracts.md` §7 (`StructureTreeNode`), §8 (evolution model), §9
(drawer URL), §11 (JSON element types).

## Implementation steps

### Step 1 — Universal ParametersTab component

```tsx
// parameters-tab.tsx
export interface ParametersTabProps {
  runId?: string;          // when in algorithm detail (one run)
  hashContent?: string;    // when in agent group (many runs)
  scope: "run" | "group";  // selects data source
}

export function ParametersTab({ runId, hashContent, scope }: ParametersTabProps) {
  // 1. fetch agent_graph (from runId or latest run of the group)
  // 2. fetch /runs/.../parameters per leaf (or aggregated /api/agents/.../parameters)
  // 3. build StructureTree from graph + parameters
  // 4. render <StructureTree /> with onSelectParameter -> drawer.open
  // 5. when drawer.paramPath set: fetch /runs/.../parameter-evolution/<path>
  //    OR aggregate per-instance evolution from /api/agents/.../parameters
  // 6. render <ParameterDrawer><ParameterEvolutionView /><WhyPane /></ParameterDrawer>
}
```

Two scopes:

- `scope="group"`: data source is agent-group-wide (across N
  invocations). Endpoint chain: `/api/agents/{hash}/parameters` for
  the per-run snapshots; for evolution, derive from the
  cross-run snapshots (no per-step gradient — gradients are a
  per-run training concept).
- `scope="run"`: data source is a single algorithm run. Endpoint
  chain: `/runs/{runId}/agent_graph` plus
  `/runs/{runId}/parameter-evolution/{path}` for the timeline. This
  is where the gradient + tape context is rich.

The Why pane only renders meaningful content in `scope="run"` (since
gradients are per-run); in `scope="group"`, fall back to
"this view aggregates across N invocations; open a run for full
gradient context".

### Step 2 — Wire into agent group Training tab

Replace the entire current body of `AgentGroupTrainTab.tsx` with:

```tsx
return (
  <div className="h-full overflow-auto p-4">
    <ParametersTab hashContent={hashContent} scope="group" />
  </div>
);
```

Drop the `Train`-named summary block, the `ParameterEvolution` lane
grid, and the `Drift events` panel. The lane-grid view is fully
superseded by StructureTree + per-type views.

The Drift events stay on the single-invocation Drift tab
(`SingleInvocationDriftTab.tsx`); they are a per-run concept.

### Step 3 — Wire into algorithm JSON layouts

Each mutating algorithm's JSON layout adds a tab:

```json
{ "id": "parameters", "label": "Parameters" }
```

and an element:

```json
"parameters": {
  "type": "ParametersTab",
  "props": { "runId": "$context.runId", "scope": "run" }
}
```

Touched layouts: `trainer.json`, `evogradient.json`, `opro.json`,
`selfrefine.json`. The user-facing tab order (per
`00-contracts.md` §11) keeps Parameters near the right side of the
strip, before Agents/Events.

### Step 4 — Register element

`dashboard-renderer.tsx` resolves element types via a registry. Add:

```ts
case "ParametersTab":
  return <ParametersTab {...resolvedProps} />;
```

(Or wherever the registry is — the runtime resolver may use a map
object; follow the existing pattern.)

### Step 5 — Empty states

When the agent has no trainable parameters (rare for mutating algos;
should not happen, but handle it): render `EmptyState` with
"this run / this group has no trainable parameters; the algorithm
has no gradient targets".

## Design alternatives

1. **Two separate tab components for run vs group scope vs one
   parameterized.** Recommendation: one parameterized — the data
   model is the same shape, scope just selects the source.
2. **Drawer rendered inside the tab vs portal-rendered at app
   level.** Recommendation: portal (matches brief `03-02` decision).
3. **Pre-render the StructureTree in the JSON layout vs let the
   ParametersTab own it.** Recommendation: own it; the tree shape is
   a runtime concern, not a layout concern.

## Acceptance criteria

- [ ] On a non-trainable agent, the Training tab is hidden (already
  enforced by brief `02-04`).
- [ ] On a trainable agent group (e.g. example 03), the Training tab
  shows the StructureTree.
- [ ] Clicking a trainable parameter row opens the drawer with the
  right per-type evolution view.
- [ ] On a Trainer / EvoGradient / OPRO / SelfRefine algorithm run,
  the Parameters tab shows the same StructureTree + drawer.
- [ ] In algorithm scope, the WhyPane renders gradient context for
  the selected step (when emitted by the optimizer).
- [ ] `?param=...&step=N` URLs deep-link to a specific parameter and
  step.
- [ ] `pnpm test --run` passes; `make build-frontend` succeeds.
- [ ] `apps/frontend/src/layouts/LayoutResolver.test.ts` still passes.

## Test plan

- `parameters-tab.test.tsx`: render in both scopes with fixtures.
- Layout JSON parse test (existing) covers the new tabs.
- Manual end-to-end on examples 03 and 04: open Training tab, click
  a trainable parameter, see evolution + gradient.

## Out of scope

- The per-algorithm bespoke tabs (Sequence 5).
- The PromptTraceback reader (brief `06-05`).
- Tape view (brief `06-06`).

## Stretch goals

- A "compare two parameters" mode: shift-click two trainable rows in
  the StructureTree → drawer renders both timelines side by side.
- Add a small "show only changed" filter chip in the StructureTree
  header that hides parameters with `points.length <= 1`.
- Clicking a non-trainable parameter row reveals its current value
  inline (collapsible) without opening the drawer.
