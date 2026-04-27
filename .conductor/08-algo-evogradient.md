# 08 — Algorithm: EvoGradient

**Stage:** 3 (parallel; depends on Briefs 01, 02, 15)
**Branch:** `dashboard-redesign/08-algo-evogradient`
**Subagent group:** D (Algos-creative)

## Goal

EvoGradient is the operad-unique gem: a population search where each
"individual" is an Agent and each "mutation" is a typed structural
edit (`AppendRule`, `EditTask`, `SetRole`, etc.). The view should make
the *evolution itself* visible: fitness over generations, population
diversity, operator success, and the **lineage of survivors** with
their **prompt diffs**. The Lineage and Best-individual-diff tabs are
unique to operad — they have no W&B equivalent and are the killer
feature.

This is a high-creativity brief. Use the existing chart components
(FitnessCurve, PopulationScatter, MutationHeatmap, OpSuccessTable,
OperatorRadar) but compose them into a story.

## Read first

- `operad/optim/optimizers/evo.py` — `EvoGradient.step()` lines
  174-245; `_emit_generation_event` lines 279-322. Each generation
  emits:
  ```
  generation: {
    gen_index, population_scores, survivor_indices,
    mutations: [{individual_id, op, path, improved}, …],
    op_attempt_counts, op_success_counts
  }
  ```
- `operad/utils/ops.py` — typed `AppendRule`, `EditTask`, `SetRole`,
  `DropRule`, `ReplaceRule`. Each op has `apply(agent)` and `undo`. The
  `path` is a dotted path to the sub-agent the op targets.
- `apps/dashboard/operad_dashboard/runs.py:337-352` — `RunInfo.generations[]`
  aggregation.
- `apps/dashboard/operad_dashboard/routes/{fitness,mutations}.py`.
- `apps/frontend/src/components/charts/{fitness-curve,population-scatter,mutation-heatmap,op-success-table,operator-radar,prompt-drift-diff,multi-prompt-diff}.tsx`.
- `apps/frontend/src/layouts/evogradient.json` — current shape.
- `INVENTORY.md` §19 (typed in-place mutations), §21 (Parameter family
  — EvoGradient mutates them), `operad/optim/README.md`.

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/evogradient/evo-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/evogradient/evo-evolution-tab.tsx`
  (re-uses FitnessCurve + adds spread band)
- `apps/frontend/src/components/algorithms/evogradient/evo-population-tab.tsx`
  (PopulationScatter + survivor highlighting)
- `apps/frontend/src/components/algorithms/evogradient/evo-operators-tab.tsx`
  (radar + heatmap + success table side-by-side)
- `apps/frontend/src/components/algorithms/evogradient/evo-lineage-tab.tsx`
  **(new — the survivor lineage tree)**
- `apps/frontend/src/components/algorithms/evogradient/evo-bestdiff-tab.tsx`
  **(new — per-generation best-individual diff)**

Edit:

- `apps/frontend/src/layouts/evogradient.json` — fill the per-algo tabs.
- `apps/frontend/src/components/algorithms/evogradient/registry.tsx` —
  register the new components.

## Tab structure

```
[ Overview ] [ Evolution ] [ Population ] [ Operators ] [ Lineage ]
[ Best diff ] [ Agents ] [ Events ] [ Graph ]
```

That's 9 tabs total — heavy, but each is a distinct angle on the same
data. EvoGradient is the heaviest algorithm in the system; its tab set
matches.

### Overview

```
─── status strip ────────────────────────────────────
[ ● live | ended ]   gen 12 / 50   pop 8   best 0.91   total cost $0.42

─── headline: fitness curve (existing) ──────────────
Best / mean / worst lines, generation x-axis. The mean line is the
moving target; the spread band (worst→best) shows diversity collapse.

─── operator radar (existing) ───────────────────────
Per-op success rate as a radar plot. Catches when one mutation type
dominates.

─── KPI row ─────────────────────────────────────────
[ population size ] [ generations ] [ survivors per gen ]
[ ops attempted ]   [ ops succeeded ] [ wall time ]
```

### Evolution (existing chart, expanded)

```
─── fitness curve (large) ─────────────────────────
Best / mean / worst lines + the *spread band* (filled area between
worst and best per generation). Click a generation → opens the Best
diff tab pinned to that generation.

─── per-individual fitness paths ─────────────────
N transparent thin lines (one per population slot), connecting each
slot's score across generations (when survivors are kept by index).
Survivors are bold; eliminated individuals fade out.
```

The "per-individual fitness paths" is new. Computing it requires
walking the `survivor_indices` lineage backwards. When an individual
is replaced (its slot's index is not in survivors), the line ends.

### Population

`PopulationScatter` (existing) per generation. Add:
- A generation slider at the top to scrub through generations.
- Survivors filled, eliminated hollow.
- Hover on a point shows the individual's mutations applied since the
  initial agent.

### Operators

A `PanelGrid cols={2}`:

```
[ MutationHeatmap (existing) ]    [ OpSuccessTable (existing) ]
[ OperatorRadar (existing)   ]    [ Per-path success table   ]
```

`Per-path success table` is new: groups op attempts by the *targeted
sub-agent path*, showing which sub-agents the optimizer most frequently
mutates and which mutations succeed there. Sourced from
`generation.mutations[].{path, op, improved}`.

### Lineage (NEW — the killer feature)

A vertical tree where each node is a generation's *survivor of choice*
(the survivor with the highest score), and the edges represent which
op produced which survivor. Layout: top = gen 0 (initial), bottom =
last gen.

```
gen 0   [ initial agent · score 0.42 ]
           │ AppendRule(path=Reasoner, "Be concise")
           ▼
gen 1   [ score 0.51 ]
           │ ReplaceRule(path=Reasoner, idx=2)
           ▼
gen 2   [ score 0.59 ]
           │ EditTask(path=Reasoner)
           ▼
gen 3   [ score 0.67 ]
…
```

Click a node → opens the **Best diff tab** scoped to that generation.

When multiple survivors per generation are kept (top_k > 1), the tree
fans out: gen N has multiple children. Render only the lineage that
ends in the final winner; lighter branches show the alternative
survivors that were dropped later.

Implementation: `@xyflow/react` (already a dep) with a top-down dagre
layout. Each node is a small card showing score + a single-line preview
of the op applied. Edges are labeled with `op_name(path)`.

When `gen_index` only has one survivor (typical), the tree degenerates
to a vertical chain — still valuable.

### Best diff (NEW — also unique)

For each generation, render a `MultiPromptDiff` (existing primitive)
showing the survivor's full agent state diff against the previous
survivor. URL `?gen=3` pins the generation. Default = latest.

The diff structure:

```
─── Generation 3 (best, score 0.67 → 0.91, +0.24) ──
Path: Reasoner

role:        (unchanged)
task:        - "Write a clear answer"
             + "Write a clear, concise answer in 3-5 sentences."
rules:
  rule 0:     "Cite at least one mechanism." (unchanged)
  rule 1:    -"Use plain language."
             +"Use plain language; explain technical terms in
                parentheses if needed."
examples:    (unchanged)
config.sampling.temperature:  0.7 → 0.4
```

The diff for non-text params (Float, Categorical, Configuration) renders
as `(before) → (after)` with directional color.

This is the inventory's §19 (typed mutations) and §21 (Parameter
family) being made visible. No W&B equivalent.

### Agents tab

Universal. For EvoGradient, the synthetic children are the per-
individual evaluations across generations — ~`pop * dataset_size *
generations` rows. Default `groupBy: "hash"` collapses cleanly.
Override (in `evogradient.json`):

```json
"agents": {
  "type": "AgentsTab",
  "props": {
    "runId": "$context.runId",
    "groupBy": "hash",
    "extraColumns": ["gen", "individual_id"]
  }
}
```

## Design alternatives

### A1: Lineage rendering

- **(a)** xyflow vertical tree (recommended).
- **(b)** A nested list with indentation. **Reject:** loses the visual
  branching when top_k > 1.
- **(c)** A sequence diagram via Mermaid. **Reject:** Mermaid is heavy
  and the layout for 50 generations is unreadable.

### A2: Best diff scope

- **(a)** Per-generation diff (recommended; fits the lineage flow).
- **(b)** Cumulative diff against initial agent. Useful but harder to
  understand at a glance. Provide a toggle: "vs previous gen" /
  "vs initial".

### A3: When pop_size is large (>20)

- **(a)** Population scatter still works (recommended). 20 dots per
  generation is fine.
- **(b)** Switch to a heatmap (gen × score-bucket). **Defer:** unless
  someone runs pop_size=100, the scatter is enough.

### A4: Backend delta?

EvoGradient already emits everything needed for tabs except *the
agent-state per survivor* (for the Best diff). To compute diffs, the
frontend would have to load the synthetic child of each survivor's
evaluation and read the agent's state from the `metadata.state_snapshot`
(which `agent_routes.py:707-759` already exposes via `/runs/:id/agent/:path/diff`).

Strategy: cache the latest generation's survivor state by reading the
last synthetic child's `state_snapshot`. Compare two survivors via the
existing `/runs/:id/agent/:path/diff` route, with `from` and `to` set
to the corresponding invocation ids.

If the existing diff endpoint returns an `AgentDiff` shape that
`MultiPromptDiff` can consume, no backend changes are needed. If not,
add a new `/api/algorithms/:runId/best-diff?gen=<n>` endpoint in
Brief 14.

## Acceptance criteria

- [ ] Tabs render:
  `Overview · Evolution · Population · Operators · Lineage · Best diff · Agents · Events · Graph`.
- [ ] Overview surfaces fitness curve, operator radar, KPI strip.
- [ ] Evolution tab shows per-individual fitness paths overlaid on the
  best/mean/worst.
- [ ] Population tab has the generation slider; URL `?gen=N` pins.
- [ ] Operators tab has the new per-path success table.
- [ ] Lineage tab renders the survivor tree using xyflow; clicking a
  node opens Best diff with that generation pinned.
- [ ] Best diff tab renders a structured diff per Parameter type
  (text → MultiPromptDiff; numeric → before→after; config → KeyValueGrid
  side-by-side). Vs-initial toggle works.
- [ ] Agents tab respects the EvoGradient override.
- [ ] `pnpm test --run` green; `make build-frontend` green.

## Test plan

- **Unit:** `evo-lineage-tab.test.tsx` (xyflow node creation correctness),
  `evo-bestdiff-tab.test.tsx` (per-Parameter rendering),
  `evo-evolution-tab.test.tsx` (per-individual paths).
- **Visual:** screenshots of all tabs against `examples/04_evolutionary.py`
  at gen 5+.
- **Performance:** Lineage with 50 generations should render in <500ms;
  measure via `console.time` in dev mode.

## Out of scope

- Backend `/api/algorithms/:runId/best-diff` (only needed if existing
  endpoints don't suffice; document the decision in the PR).
- Universal tabs (Brief 15).
- Backend payload changes (Brief 14 if any are required for cleaner
  state-snapshot access).

## Hand-off

PR body with checklist + screenshots of all 8 tabs. The Lineage and
Best diff tabs are the marquee shots; include both close-up and
zoomed-out views.
