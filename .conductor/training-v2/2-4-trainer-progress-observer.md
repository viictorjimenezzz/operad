# 2-4 — `TrainerProgressObserver` + dashboard progress widget

**Wave.** 2. **Parallel with.** 2-{1,2,3,5}. **Depends on.** 1-2.

## Context

`Trainer.fit(epochs=N)` has no visible progress indicator. With 1-2
emitting `batch_start` / `batch_end` events, we can add a
terminal-side observer (Rich progress bar) and a matching dashboard
widget.

## Scope — in

### `operad/train/progress.py` (new file)

```python
class TrainerProgressObserver:
    """Render a Rich progress bar for `Trainer.fit`.

    Listens for `algo_start` (epochs total), `batch_start` /
    `batch_end` (advances the inner bar), and `on_epoch_end`
    (advances the outer bar). Gracefully no-ops when `rich` is not
    installed."""

    def __init__(self, *, transient: bool = False) -> None: ...
    async def on_event(self, event) -> None: ...
```

Expose `TrainerProgressObserver` from `operad/train/__init__.py`.

Render two nested Rich progress bars:
- outer: "epoch 2/5" with a bar filled by completed epochs;
- inner: "batch 17/80 (14.2 batch/s)" with a bar filled by batches
  within the current epoch.

Gracefully hide the inner bar when total batch count is unknown
(e.g., streaming dataset).

### `apps/dashboard/operad_dashboard/routes/progress.py` (new)

- `GET /runs/{run_id}/progress.json` — returns
  `{epoch, epochs_total, batch, batches_total, elapsed_s,
    rate_batches_per_s, eta_s}`, computed from the most-recent
  `batch_start`/`batch_end`/`algo_start` events.
- `GET /runs/{run_id}/progress.sse` — streams updates.

### `apps/dashboard/operad_dashboard/templates/partials/_progress.html` (new)

- Two stacked HTML `<progress>` elements (native), one per nesting
  level, plus a text row showing ETA and batch rate.

### `apps/dashboard/operad_dashboard/static/js/progress.js` (new)

- EventSource listener → updates `<progress>.value` and text.

### `apps/dashboard/operad_dashboard/app.py`

- Include new router; embed `_progress.html` near the top of run
  detail (above fitness chart).

### Tests

- `tests/train/test_progress_observer.py`: instantiate the observer,
  push synthetic events, confirm state (current_epoch, current_batch,
  total_batches) tracks correctly.
- `apps/dashboard/tests/test_progress.py`: endpoint returns expected
  shape for a seeded event history.

## Scope — out

- Do not add a pause / cancel button (that'd require bidirectional
  control; deliberately out of scope for read-only observers).
- Do not implement distributed progress aggregation (multi-worker
  training is a different slot).
- Do not spinner-style fallback when Rich absent — just silently
  no-op.

## Dependencies

- 1-2: `batch_start` / `batch_end` events.
- `rich` (optional extra).

## Design notes

- **Rich install gate.** Import `rich` lazily; observer's
  constructor raises a clear `ImportError` with install hint only
  when Rich-specific features would be used (deferred).
- **ETA calculation.** Exponential moving average of per-batch
  duration, weighted toward recent batches, clamped to ≥ 1s.
- **Reconnection on dashboard.** If the browser reconnects
  mid-run, the SSE endpoint replays the latest snapshot from the
  event store so the progress bar doesn't start from zero.

## Success criteria

- `pytest tests/train/test_progress_observer.py
  apps/dashboard/tests/test_progress.py` passes.
- `examples/train_demo.py` with the observer registered shows a
  live progress bar in the terminal.
- Dashboard run-detail page shows live progress bars during
  `examples/talker_evolution.py --dashboard`.
