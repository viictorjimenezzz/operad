# 05-06 OPRO — prompt history, score curve, parameters

**Branch**: `dashboard/algo-opro`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`, `04-01`
**Estimated scope**: small

## Goal

Replace `apps/frontend/src/layouts/opro.json` with:
`Prompt history · Score curve · Parameters · Agents · Events`.

OPRO (LLM-as-optimizer) iterates over (prompt, score) pairs. The
prompt-history ladder is the headline.

## Files to touch

- `apps/frontend/src/layouts/opro.json` — replace.
- `apps/frontend/src/components/algorithms/opro/prompt-history-tab.tsx` —
  new (or wrap existing `MultiPromptDiff`).
- `apps/frontend/src/components/algorithms/opro/score-curve-tab.tsx` —
  new (or wrap existing `ConvergenceCurve`).
- Tests.
- `apps/frontend/src/components/algorithms/registry.tsx`.

## Contract reference

`00-contracts.md` §11, §15 (OPRO emit must include `text`, `score`,
`prev_best`).

## Implementation steps

### Layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "history", "label": "Prompt history" },
      { "id": "score", "label": "Score curve" },
      { "id": "parameters", "label": "Parameters" },
      { "id": "agents", "label": "Agents", ... },
      { "id": "events", "label": "Events", ... }
    ]
  }
}
```

### Prompt history tab

Vertical ladder of (iteration, prompt, score). Each row shows the
prompt diff vs the previous (`MultiPromptDiff` works here). Click a
row → opens the parameter drawer with that step selected.

### Score curve tab

Use `ConvergenceCurve` (existing). Mark the iterations where
`prev_best` improved with a small green dot.

### Parameters tab

`ParametersTab` with `scope="run"`. The OPRO target parameter is the
prompt; the per-type evolution view is `text` (brief `03-03`).

## Acceptance criteria

- [ ] OPRO runs render the new tab strip.
- [ ] Prompt history shows the ladder; clicking a row opens the
  drawer at that step.
- [ ] Score curve marks improvements.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Prompt history adds a "show only improvements" filter.
- Side-by-side compare: select two iterations → drawer renders both
  prompts with a unified diff.
