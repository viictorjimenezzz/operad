# 05-04 EvoGradient — lineage, population, operators, parameters

**Branch**: `dashboard/algo-evogradient`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`, `04-01` (`ParametersTab`)
**Estimated scope**: medium

## Goal

Replace `apps/frontend/src/layouts/evogradient.json` with:
`Lineage · Population · Operators · Parameters · Agents · Events`.
The new bespoke component is **Lineage** — a generation-by-generation
DAG showing parent→offspring relationships.

## Why this exists

EvoGradient survives via mutation-selection across generations. The
fitness curve and population scatter already exist; the lineage view
is the missing "who came from whom" story. The Parameters tab
(brief `04-01`) shows the parameters being mutated.

## Files to touch

- `apps/frontend/src/layouts/evogradient.json` — replace.
- New: `apps/frontend/src/components/algorithms/evogradient/lineage-tab.tsx`.
- New: `apps/frontend/src/components/algorithms/evogradient/lineage-tab.test.tsx`.
- `apps/frontend/src/components/algorithms/registry.tsx` — register.

## Contract reference

`00-contracts.md` §3 (palette), §11.

## Implementation steps

### Step 1 — Layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "lineage", "label": "Lineage" },
      { "id": "population", "label": "Population" },
      { "id": "operators", "label": "Operators" },
      { "id": "parameters", "label": "Parameters" },
      { "id": "agents", "label": "Agents", ... },
      { "id": "events", "label": "Events", ... }
    ]
  }
}
```

### Step 2 — `EvoLineageTab`

Generation columns × individual rows. Each individual is a small
node colored by its score (sequential ramp `--color-err` →
`--color-ok`). Edges connect each individual to its parent (read
from the `survivor_indices` already in `generation` events at
`runs.py:386-399`).

Hover an individual → tooltip with score + the mutation operator
applied to it. Click → opens the synthetic child run.

Layout: simple SVG with x = gen index, y = individual index. Edges
drawn as cubic curves.

### Step 3 — Population tab

Reuse `population-scatter.tsx` (existing). Add a generation playbar
under it: a slider that advances through generations, animating the
scatter.

### Step 4 — Operators tab

Reuse `OperatorRadar` (existing). Replace any wrapper that adds a
bordered card.

### Step 5 — Parameters tab

JSON layout entry uses `ParametersTab` (from brief `04-01`):

```json
"parameters": {
  "type": "ParametersTab",
  "props": { "runId": "$context.runId", "scope": "run" }
}
```

## Design alternatives

1. **Lineage as DAG vs tree (best individual back-tracked).**
   Recommendation: DAG — shows the full population dynamics, not just
   the winning ancestry.
2. **Color individuals by score vs by generation.** Recommendation:
   by score; generation is already encoded in x.

## Acceptance criteria

- [ ] EvoGradient runs render the new tab strip.
- [ ] Lineage tab renders one column per generation; each individual
  links to its parent.
- [ ] Population tab has a generation playbar.
- [ ] Parameters tab renders the StructureTree + drawer.
- [ ] `pnpm test --run` passes; layout JSON parse passes.

## Test plan

- `lineage-tab.test.tsx`: 3-gen × 5-individual fixture; assert 15
  nodes, 10 edges (5 parent links per non-initial gen).

## Stretch goals

- Click an individual node → open the WhyPane in a side drawer with
  the gradient text that produced that individual.
- A "best individual highlight" toggle that bolds the survivor
  ancestry chain.
- A "show only survivors" filter that dims dead branches.
