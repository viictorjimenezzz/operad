# 05-07 SelfRefine — refine ladder, iterations, parameters

**Branch**: `dashboard/algo-selfrefine`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`, `04-01`
**Estimated scope**: small

## Goal

Replace `apps/frontend/src/layouts/selfrefine.json` with:
`Refine ladder · Iterations · Parameters · Agents · Events`.

## Why this exists

SelfRefine runs `Generator → Reflector → Refiner` per iteration. The
canonical view is a 3-column ladder where each iteration is a row
and each phase a column.

## Files to touch

- `apps/frontend/src/layouts/selfrefine.json` — replace.
- New: `apps/frontend/src/components/algorithms/selfrefine/refine-ladder-tab.tsx`.
- Tests.
- `apps/frontend/src/components/algorithms/registry.tsx`.

## Contract reference

`00-contracts.md` §11.

## Implementation steps

### Layout

```json
{
  "tabs": [
    { "id": "ladder", "label": "Refine ladder" },
    { "id": "iterations", "label": "Iterations" },
    { "id": "parameters", "label": "Parameters" },
    { "id": "agents", "label": "Agents", ... },
    { "id": "events", "label": "Events", ... }
  ]
}
```

### Refine ladder tab

Grid: rows = iterations, columns = `[generator, reflector, refiner]`.
Each cell shows a markdown preview of that phase's output, truncated
to 4 lines, with hover-expand.

The cell border-color = score band (ok/warn/err) based on the phase
score. The right edge of each iteration row shows
`refine_score (kind:"score")`.

Click a cell → opens a side-drawer with the full phase output.

### Iterations tab

`RunTable` with columns: `iter · refine_score (score) · stop_reason
(text) · langfuse →`.

### Parameters tab

`ParametersTab` (from `04-01`).

## Acceptance criteria

- [ ] SelfRefine runs render the new tab strip.
- [ ] Refine ladder shows N rows × 3 columns; cells are clickable.
- [ ] Iterations tab uses `RunTable`.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Highlight the row where the run stopped (stop_reason ≠ "max_iter").
- Add a "show only improvements" filter on the ladder.
