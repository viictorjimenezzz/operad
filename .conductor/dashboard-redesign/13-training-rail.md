# 13 — Training rail

**Stage:** 4 (parallel-able with Stage 3 backend; lands last because
it depends on all backend deltas + Brief 15)
**Branch:** `dashboard-redesign/13-training-rail`
**Subagent group:** D (Algos-creative) or executed in Stage 4

## Goal

The Training rail is operad's most W&B-natural domain: optimization
loops with loss curves, LR schedules, gradients, checkpoints, and
prompt drift. The view should compose all of these into a workspace
that, on opening, gives the user *the picture* of how training is
going. Plus two operad-unique tabs: per-parameter small multiples
(Parameter evolution at the training granularity) and the
**PromptTraceback** tab — there is no W&B equivalent.

## Read first

- `operad/train/trainer.py` — `Trainer.fit()` lines 145-213; emit sites
  inline through `_fit_loop` lines 215-489. Key events:
  - `algo_start`: `{epochs, seed_hash_content, batch_size}`
  - `iteration phase="epoch_start"`: `{phase, epoch}`
  - `batch_end`: `{phase, epoch, batch, step, train_loss, lr, lr_groups}`
  - `gradient_applied` (kind extension): `{epoch, batch, message,
     severity, target_paths, by_field, applied_diff}`
  - `iteration phase="epoch_end"`: `{phase, epoch, train_loss, val_loss,
     lr, lr_groups, hash_content, checkpoint_score, parameter_snapshot}`
  - `algo_end`: `{epochs_completed, final_hash_content}`
- `operad/train/callbacks/promptdrift.py` — emits `iteration` under
  `algorithm_path="PromptDrift"`, sharing the trainer run_id.
- `operad/data/loader.py:355-385` — DataLoader's `batch_start` /
  `batch_end` events.
- `operad/optim/backprop/traceback.py` — `PromptTraceback` artifact
  (Brief 14 ships persistence).
- `apps/dashboard/operad_dashboard/routes/{progress,fitness,checkpoints,gradients,drift}.py`
  — backend wiring.
- `apps/frontend/src/components/charts/{training-loss-curve,lr-schedule-curve,training-progress,checkpoint-timeline,gradient-log,drift-timeline,prompt-drift-diff,multi-prompt-diff}.tsx`
  — every chart we need.
- `apps/frontend/src/dashboard/pages/TrainingIndexPage.tsx` — current
  index; will be redesigned.
- `apps/frontend/src/layouts/trainer.json` — current layout.
- `INVENTORY.md` §21 (Training & optimization), §22 (PromptTraceback),
  `TRAINING.md`, `operad/optim/README.md`, `operad/train/README.md`.

## Files to touch

Create:

- `apps/frontend/src/dashboard/pages/TrainingIndexPage.tsx` — replace
  contents.
- `apps/frontend/src/dashboard/pages/run-detail/TrainingDetailLayout.tsx`
  is owned by Brief 02; this brief fills the panels.
- `apps/frontend/src/components/algorithms/trainer/training-workspace.tsx`
  — the default workspace panel grid.
- `apps/frontend/src/components/algorithms/trainer/parameter-evolution-multiples.tsx`
  — small multiples, one per parameter.
- `apps/frontend/src/components/algorithms/trainer/training-compare-panel.tsx`
  — overlay charts when multiple training runs are selected.
- `apps/frontend/src/components/algorithms/trainer/prompt-traceback-view.tsx`
  — the new Traceback tab.
- `apps/frontend/src/dashboard/pages/run-detail/TrainingTracebackTab.tsx`

Edit:

- `apps/frontend/src/layouts/trainer.json` — fill the per-algo tabs.
- `apps/frontend/src/components/algorithms/trainer/registry.tsx`.
- `apps/frontend/src/components/panels/section-sidebar/training-tree.tsx`
  — multi-select support for compare mode.

## Index `/training`

```
─── KPI strip ────────────────────────────────────
 8 trainee instances     17 training runs     best score 0.91
 total epochs run: 142   total wall: 6h 13m

─── trainee table (RunTable, grouped by trainee hash) ─
[●●][State][Trainee class][hash][# runs][best score][last run epochs][cost][sparkline]
…
```

Click a row → `/training/:runId` for the most recent run of that
trainee. The Sidebar Training tree is the deeper navigation.

Multi-select two or more runs → "Compare →" pushes to
`/training?compare=runId1,runId2` which loads a compare-shape page
(see Compare mode below).

## Detail page `/training/:runId`

Tab structure:

```
[ Workspace ] [ Loss ] [ Parameters ] [ Drift ] [ Gradients ]
[ Checkpoints ] [ Progress ] [ Traceback ] [ Agents ] [ Events ] [ Graph ]
```

(Traceback is conditional on `summary.has_traceback`, set by Brief 14
when `PromptTraceback` artifacts are persisted.)

### Workspace (the headline tab)

```
┌──────────────────────────────┬──────────────────────────────┐
│ Loss curve (train + val)     │ LR schedule                  │
├──────────────────────────────┼──────────────────────────────┤
│ Gradient log (latest 5)      │ Checkpoint timeline           │
├──────────────────────────────┴──────────────────────────────┤
│ PromptDrift timeline (epoch × hash diff + changed paths)   │
├─────────────────────────────────────────────────────────────┤
│ Per-parameter small multiples (3-up)                        │
└─────────────────────────────────────────────────────────────┘
```

Each panel is a `PanelCard` wrapping the existing chart component. A
"View full" affordance in each header opens the corresponding
dedicated tab.

The grid is **not** drag-resizable (forbidden in `00-CONTRACTS.md` §8);
it's a static `PanelGrid` with sized cells.

### Loss

Full-width `TrainingLossCurve`. Add toggles:
- Show train / val / both.
- Smooth (EMA window 5).
- Mark best epoch (already in chart).

### Parameters (NEW, replaces or augments the existing Drift tab)

`ParameterEvolutionMultiples` is a small-multiples grid: one card per
trainable Parameter path. Each card shows that parameter's value
evolution over epochs (sourced from
`iteration phase="epoch_end".parameter_snapshot`).

For text parameters: a value-hash lane chart (same shape as Brief 04
Train tab). For numeric: a line. For categorical: a step plot.

Click a card → opens a side panel with the full diff between any two
selected epochs.

### Drift

The existing `DriftTimeline` (full size). Each entry shows
before/after with a `PromptDriftDiff` rendering. Clicking an entry
deep-links to the matching `gradient_applied` event (correlated by
epoch) for context.

### Gradients

`GradientLog` (existing) full-page. Add filters: by severity (`>= 0.5`,
all), by `target_paths`. Clicking a gradient row → expands inline
showing the `applied_diff` rendered with `MultiPromptDiff`.

### Checkpoints

`CheckpointTimeline` (existing) full-page. Click a checkpoint → side
panel with the parameter snapshot at that epoch and a "Reload from
checkpoint" CTA (links to a future API; render disabled with tooltip
for now, like the agent group's "Promote to training run").

### Progress

`TrainingProgress` (existing) full-page. Adds:
- ETA prominent at top.
- Batch matrix (epoch × batch index, color = batch loss). Use
  `recharts` heatmap or hand-rolled SVG (the matrix is small —
  ≤ 20 epochs × 100 batches).

### Traceback (NEW, conditional)

When the run has persisted `PromptTraceback` artifacts (Brief 14
implements persistence), this tab renders them. Otherwise the tab is
hidden.

```
─── traceback (epoch 3, batch 12 — severity 0.84) ────
[Frame 1] (innermost)
  agent_path: Reasoner.stage_2
  inputs:    [Markdown]
  output:    [Markdown]
  gradient:  "tighten the wording: …"

[Frame 2]
  agent_path: Reasoner.stage_1
  inputs:    [Markdown]
  output:    [Markdown]
  gradient:  "the prior stage's…"
…

[ Open as NDJSON download ]
[ Open in Studio (when attached) ]
```

Each frame is a `CollapsibleSection`. Default-expanded for the top
frame, collapsed for the rest.

### Agents

Universal. Synthetic children = per-row training invocations, OPRO
proposals, etc. Override `groupBy: "hash"` is correct.

### Events

Universal.

### Graph

`AgentFlowGraph` of the trainee.

## Compare mode

`/training?compare=:runIdA,:runIdB`:

```
─── compare header ─────────────────────────────────
[ run A: hash 7f3a· · 5 epochs · 0.84 ] vs [ run B: hash 7f3a· · 5 epochs · 0.91 ]

─── overlaid loss curves ───────────────────────────
(A in --qual-1, B in --qual-7, identity-color stable)

─── overlaid LR schedules ──────────────────────────
…

─── per-parameter side-by-side small multiples ─────
For each Parameter path, two columns A / B with their evolution.

─── final-state diff ───────────────────────────────
Diff between A's final agent state and B's.
```

The compare URL deep-links from the index multi-select. No drawer
(Q3 = skip). Single shared page.

## Design alternatives

### A1: Workspace panel order

- **(a)** Loss + LR top, Gradients + Checkpoints middle, Drift + Param
  multiples bottom (recommended; most-glanceable on top).
- **(b)** Param multiples top. **Reject:** few users care about
  individual Parameter values until something breaks.

### A2: Compare via shared page or tabs

- **(a)** Shared page (recommended; keeps URLs reasonable).
- **(b)** A "Compare" tab on each detail page that reads a query
  param. **Reject:** asymmetric — one of the runs is the "host".

### A3: PromptTraceback formats

- **(a)** Inline expandable frames in the tab (recommended).
- **(b)** Open in modal. **Reject:** breaks deep-link flow.
- **(c)** Side panel. Defer; the inline form is enough for a first cut.

### A4: Studio integration

- **(a)** A "Studio" badge + cross-link button on Trainer runs that
  have the `HumanFeedbackCallback` attached (recommended; the inventory
  §21 mentions this).
- **(b)** Embedded Studio. **Reject:** out of scope; Studio is its own
  app.

## Acceptance criteria

- [ ] Index `/training` is a `RunTable` of trainees with KPI strip.
- [ ] `/training/:runId` tabs:
  `Workspace · Loss · Parameters · Drift · Gradients · Checkpoints · Progress · Traceback? · Agents · Events · Graph`.
- [ ] Workspace panel grid renders all 6 panels with "View full"
  affordances.
- [ ] Parameters tab renders small multiples per trainable path.
- [ ] Compare mode at `/training?compare=A,B` works end-to-end:
  multi-select in the sidebar pushes to URL; page renders overlays.
- [ ] Traceback tab is conditional (hidden without artifacts) and
  renders the frames as collapsible cards.
- [ ] Studio badge + cross-link visible when applicable.
- [ ] `pnpm test --run` green; `make build-frontend` green.
- [ ] Manual smoke: example `examples/03_training.py` (OPRO over
  `task` parameter) — verify Parameters tab shows the `task` evolution
  with diffs.

## Test plan

- **Unit:** `training-workspace.test.tsx`,
  `parameter-evolution-multiples.test.tsx`,
  `training-compare-panel.test.tsx`,
  `prompt-traceback-view.test.tsx`.
- **Layout schema:** `trainer.json` validates.
- **Visual:** screenshots of Workspace, Parameters, Traceback,
  Compare.
- **Integration:** route test for compare URL parsing.

## Out of scope

- Backend changes (Brief 14 ships PromptTraceback persistence and any
  other deltas).
- Universal tabs (Brief 15).
- The OPRO own-page rail (Brief 16) — Trainer runs that use OPRO link
  to it but the OPRO view itself lives elsewhere.

## Hand-off

PR body with checklist + screenshots. Note explicitly whether Studio
cross-link is shown for any of your test runs.
