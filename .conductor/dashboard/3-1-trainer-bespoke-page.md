# 3-1 — Trainer bespoke page

> **Iteration**: 3 of 4 (per-algorithm). **Parallel slot**: 1.
> **Owns**: the Trainer layout JSON, all training-related chart
> components, and a NEW backend route file.
> **Forbidden**: other layouts, other algorithm components, generic
> renderer/store work.

## Problem

`Trainer.fit` is operad's most information-rich algorithm: per-batch
losses, per-epoch validation, parameter drift (the actual *text* of
prompts changing over time), `TextualGradient` critiques, LR schedules,
checkpoints. Today the Trainer layout (`apps/frontend/src/layouts/
trainer.json`) renders only:

- A loss curve.
- A training-progress card (epoch/batch/ETA).
- A drift timeline showing **hashes** — not the actual prompt text
  changes.

The drift hashes are useless to a human; the gradient critiques (the
"reason" prompts changed) are not surfaced at all; LR schedules and
checkpoints have no UI.

Trainer is the one algorithm where prompt-level training really shines
— the dashboard should make that obvious.

## Scope

### Owned files

- `apps/frontend/src/layouts/trainer.json`
- `apps/frontend/src/shared/charts/training-loss-curve.tsx` (extend)
- `apps/frontend/src/shared/charts/training-progress.tsx` (extend if
  needed)
- `apps/frontend/src/shared/charts/drift-timeline.tsx` (REWRITE: from
  hash list → text-diff viewer)
- New: `apps/frontend/src/shared/charts/prompt-drift-diff.tsx` —
  three-pane (before / after / gradient critique) component.
- New: `apps/frontend/src/shared/charts/gradient-log.tsx` — chronological
  list of `TextualGradient` critiques.
- New: `apps/frontend/src/shared/charts/lr-schedule-curve.tsx` — line
  chart of LR(t).
- New: `apps/frontend/src/shared/charts/checkpoint-timeline.tsx` —
  vertical timeline of checkpoints with per-checkpoint metric snapshot.
- New: `apps/dashboard/operad_dashboard/routes/gradients.py` —
  aggregation endpoint exposing `TextualGradient` payloads from the
  registry. Mirrors how `routes/drift.py` and `routes/fitness.py` work.
- New: `apps/dashboard/operad_dashboard/routes/checkpoints.py` —
  same pattern for checkpoints.
- Tests for new components and routes.

### Forbidden files

- Other layouts (`evogradient.json`, `debate.json`, `beam.json`,
  `default.json`).
- Other agents' chart components.
- The generic renderer (2-2 owns).
- `app.py`, `runs.py`, `observer.py` (1-2 already shipped). Just add
  new files under `routes/` and register them in the existing route
  collector.

## Direction

### Backend: surface gradient & checkpoint data

The runtime emits `iteration` events from `Trainer.fit` with a `phase`
and varying payloads (e.g. `phase="batch_step"` with `loss`,
`phase="epoch_end"` with epoch metrics).

- `Trainer` callbacks may not currently emit gradient text or
  checkpoint events. **Investigate**:
  - `operad/optim/textgrad.py` — does it emit a "gradient applied"
    event with the `TextualGradient.message` text?
  - `operad/train/trainer.py` — does the "best checkpoint" callback
    emit anything observable?
- If not, **emit them** (this is operad-side; out of scope here).
  Instead, document the gap in the PR description and add a TODO in
  `routes/gradients.py` that returns mock data until the runtime
  emits real gradient events. The next iteration's coordinator can
  decide whether to widen scope.

For data the runtime *already* exposes (drift hashes, parameter
values), surface them via:

- `GET /runs/{id}/gradients.json` — returns `[{epoch, batch, by_field,
  message, severity, target_paths, applied_diff}]`.
- `GET /runs/{id}/checkpoints.json` — returns `[{epoch, score,
  parameter_snapshot}]`.

`routes/__init__.py` has a `per_run_sse()` helper — match its style.

### Drift: real text diffs

`drift-timeline.tsx` today shows a list of `(epoch, hash, changed_param_names)`.
Replace with a 3-pane diff:

- Left: parameter text at epoch N.
- Middle: parameter text at epoch N+1.
- Right: the gradient critique that caused the change.

Use `react-diff-viewer-continued` or implement with the `diff` library
+ `<pre>`. Keep highlighting minimal (added/removed lines, character-level
within lines).

For the data: drift events should carry full text (not just hashes)
once you wire the gradients route. If the registry only has hashes
today, add a way to look up the prompt text by hash via a new
endpoint or by extending `routes/drift.py`. Coordinate with the
backend implementation.

### Loss curve: train + val + LR overlay

Today's `training-loss-curve.tsx` plots a single series. Extend to:

- Train loss (solid line).
- Validation loss (dashed line, separate axis if scales differ).
- LR overlay (right-axis line).
- Highlight the best-checkpoint epoch with a vertical reference line.

Use Recharts (already in the codebase per the explore agent).

### Gradient log

A scrollable list of `TextualGradient` cards:

- Header: epoch/batch, severity badge, target_paths chips.
- Body: `message` (markdown if multi-line).
- Expandable per-field breakdown (`by_field`).

Sort newest-first; add a search filter.

### Checkpoint timeline

Vertical timeline component:

- One row per checkpoint.
- Shows: epoch, primary metric (val_loss or rubric_score), pinned-best
  badge if best.
- "Restore" button (out of scope — display only; future task wires it).

### Trainer layout

Update `trainer.json` to include:

- Tabs:
  - **Loss**: loss curve (train + val + LR + best-checkpoint marker).
  - **Drift**: prompt-drift-diff viewer (epoch slider on top).
  - **Gradients**: gradient log.
  - **Checkpoints**: checkpoint timeline.
  - **Progress**: training progress card.
  - **Graph**: agent graph (existing).
  - **Events**: existing.

Layout structure should match the auto-discovery contract that 2-2
defines.

## Acceptance criteria

1. Run a Trainer demo (look in `examples/03_train_config_temperature.py`
   or compose a small `Trainer.fit` with offline cassettes). Navigate
   to its run page → see loss curves, prompt diffs, and (if data is
   present) gradient critiques.
2. Drift tab shows actual text changes, not hashes.
3. New routes return correct shape and pass tests.
4. New chart components have unit tests with fixture data.
5. Layout JSON resolves correctly via auto-discovery from 2-2.

## Dependencies & contracts

### Depends on

- 1-1: HTTP-attach delivers all events reliably.
- 1-2: `/runs` filtering + run-aware routing.
- 2-2: layout auto-discovery + JSON-then-SSE backfill.
- 2-3: pinned-runs (a pin button in the trainer header).
- 3-5: `<LangfuseSummaryCard runId={…} />` (assume it exists; if not,
  use a placeholder div with the same shape).

### Exposes

- `<PromptDriftDiff />` and `<GradientLog />` components — other
  algorithms (Debate, in 3-2) might want to reuse the diff viewer.
- New routes: `/runs/{id}/gradients.json`, `/runs/{id}/checkpoints.json`.

## Direction notes / SOTA hints

- For diffs, `react-diff-viewer-continued` is the most-maintained
  fork; check the lockfile first.
- For multi-axis Recharts: use `<YAxis yAxisId="left" />` and
  `<YAxis yAxisId="right" orientation="right" />`.
- For markdown rendering of `message`: `react-markdown` is in the
  lockfile if shadcn or the existing event-detail panel uses it.
- For the timeline: shadcn doesn't have a built-in; build with
  flexbox + a left vertical line, ~80 lines max.

## Risks / non-goals

- Don't add training-control buttons (pause/abort/eject best). That's
  a future task; checkpoint timeline is display-only.
- Don't change the runtime's event emission surface from this task;
  document gaps and let a follow-up handle.
- Don't over-style the diff viewer; the goal is legibility, not visual
  polish.

## Verification checklist

- [ ] Backend tests for new routes pass (cd apps/dashboard && uv run
      pytest -k gradients -k checkpoints).
- [ ] Frontend tests pass (`make frontend-test`).
- [ ] Run a Trainer demo end-to-end; visually verify each tab renders.
- [ ] Drift tab shows text, not hashes.
