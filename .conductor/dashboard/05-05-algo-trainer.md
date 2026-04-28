# 05-05 Trainer — loss, schedule, drift, parameters, traceback

**Branch**: `dashboard/algo-trainer`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`, `04-01` (`ParametersTab`),
`06-05` (`PromptTraceback` reader — but this brief lands first; the
traceback tab renders an empty state until `06-05` ships)
**Estimated scope**: medium

## Goal

Replace `apps/frontend/src/layouts/trainer.json` with:
`Loss · Schedule · Drift · Parameters · Traceback · Agents · Events`.
The Trainer is the most data-rich algorithm; this brief gives every
inventory feature its dedicated home.

## Why this exists

§21 of the inventory describes Trainer as the spine of operad
training. The user wants the optimization story (gradients,
backprop, optimizer actions) — much of which the Trainer emits.

## Files to touch

- `apps/frontend/src/layouts/trainer.json` — replace.
- `apps/frontend/src/components/algorithms/trainer/` — wrappers as
  needed; reuse:
  - `TrainingLossCurve` (existing) → Loss tab.
  - `LrScheduleCurve` + `CheckpointTimeline` (existing) → Schedule.
  - `DriftTimeline` + `PromptDriftDiff` (existing) → Drift.
  - `PromptTracebackReader` (from brief `06-05`) → Traceback.
- `apps/frontend/src/components/algorithms/registry.tsx` — register.

## Contract reference

`00-contracts.md` §11, §15 (`traceback_path`).

## Implementation steps

### Layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "loss", "label": "Loss" },
      { "id": "schedule", "label": "Schedule" },
      { "id": "drift", "label": "Drift" },
      { "id": "parameters", "label": "Parameters" },
      { "id": "traceback", "label": "Traceback",
        "badge": "$queries.summary.has_traceback" },
      { "id": "agents", "label": "Agents", ... },
      { "id": "events", "label": "Events", ... }
    ]
  }
}
```

The `traceback` tab badge appears only when
`summary.has_traceback === true`.

### Loss tab

Overlay `train_loss` and `val_loss` (when present) on a single
`TrainingLossCurve`. Add a chip-strip toggle for what to overlay
(loss, accuracy, custom metrics from `metadata.metrics`).

### Schedule tab

`LrScheduleCurve` (existing). Below it, `CheckpointTimeline` showing
when `BestCheckpoint` callback fired. Mark the best epoch with a
star icon.

### Drift tab

`DriftTimeline` (existing) for the prompt-drift hash diff per epoch.
Click a drift event → opens `PromptDriftDiff` inline below.

### Parameters tab

`ParametersTab` (from brief `04-01`) with `scope="run"`.

### Traceback tab

If `summary.traceback_path` is present, render the
`PromptTracebackReader` (from brief `06-05`). Otherwise:

```tsx
<EmptyState
  title="no traceback recorded"
  description="this run did not save a PromptTraceback;
               see PromptTraceback.save() in your training script"
/>
```

## Design alternatives

1. **Drift tab vs merging Drift into Loss.** Recommendation: keep
   separate. Drift events are sparse and warrant their own canvas.
2. **Show synthetic children (per-batch invocations) on the Agents
   tab.** Recommendation: yes — `AgentsTab` already does this.

## Acceptance criteria

- [ ] Trainer runs render the new tab strip.
- [ ] Loss tab overlays train + val on one chart.
- [ ] Schedule tab shows lr + checkpoint marks.
- [ ] Drift tab works on example 03.
- [ ] Parameters tab renders the StructureTree + drawer.
- [ ] Traceback tab renders an empty state when no traceback exists,
  and the reader (when brief `06-05` lands) when one does.
- [ ] `pnpm test --run` passes; layout JSON parse passes.

## Stretch goals

- Loss tab adds a "compare across runs" toggle that overlays loss
  curves from all sibling Trainer runs of the same trainee.
- Schedule tab adds reference markers for callbacks
  (`EarlyStopping`, `BestCheckpoint`, etc.) with hover tooltips.
- Drift tab shows the changed parameter paths per drift event,
  clickable → opens the parameter drawer.
