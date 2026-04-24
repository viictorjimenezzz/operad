# 1-2 — DataLoader batch events

**Wave.** 1. **Parallel with.** 1-{1,3..6}. **Unblocks.** 2-4.

## Context

`DataLoader.__aiter__` yields `Batch`es silently. The dashboard can
only show per-generation progress for `EvoGradient`, not per-batch
progress for `Trainer.fit`. Wiring up two small events closes that
gap and feeds wave 2-4's progress widget.

## Scope — in

### `operad/runtime/events.py`

- Extend the `AlgoKind` `Literal` union with two new kinds:
  `"batch_start"`, `"batch_end"`. (Already `algo_start` / `algo_end`
  / `generation` / `round` / `cell` / `candidate` / `iteration` —
  just add two more.)
- Document the payload conventions:
  - `batch_start`: `{batch_index: int, batch_size: int,
    hash_batch: str, epoch: int | None}`.
  - `batch_end`: `{batch_index: int, batch_size: int,
    duration_ms: float, epoch: int | None}`.

### `operad/data/loader.py`

- In `DataLoader.__aiter__`, emit `batch_start` before yielding each
  `Batch` and `batch_end` immediately after the batch-consumer
  resumes. Use the existing `emit_algorithm_event` helper.
- `algorithm_path` = `"DataLoader"` (the loader is not tree-nested;
  a stable path is enough for correlation in the dashboard).
- Emission is a no-op when no observers are registered for
  `AlgorithmEvent` — the observer registry handles that silently, so
  no extra guard needed in the loader.
- `epoch` is `None` by default. The `Trainer` in 2-4 will stash the
  current epoch on a `ContextVar` so the loader can read it; expose
  a tiny helper `operad.runtime.events.set_current_epoch(n)` /
  `get_current_epoch() -> int | None` for this purpose.

### `operad/train/trainer.py`

- At the top of each epoch, call `set_current_epoch(epoch)`. At the
  end, `set_current_epoch(None)`. Do *not* emit the batch events
  yourself — the loader already does.

### Tests

- `tests/data/test_loader.py` (extend):
  - Register an `InMemoryObserver` that captures events; iterate a
    4-batch loader and assert the event sequence is
    `[batch_start, batch_end, batch_start, batch_end, ...]`.
  - Each `hash_batch` in `batch_start` matches the corresponding
    `Batch.hash_batch`.
  - `duration_ms` is non-negative and sane (< 10_000 for a no-op batch).
- `tests/train/test_trainer.py` (extend):
  - Check `epoch` is correctly propagated through batch events
    during `fit(epochs=2)`.

## Scope — out

- Do **not** emit per-sample events. Batch granularity is the floor.
- Do not modify `Batch`'s schema.
- Do not add a `BatchObserver` protocol. Consumers read the existing
  `AlgorithmEvent` stream.

## Dependencies

- Existing `operad.runtime.events` infrastructure.

## Design notes

- **Synchronicity.** `batch_start` is fired inside `__aiter__`
  immediately before `yield`. `batch_end` fires on the *next*
  iteration (or on `StopAsyncIteration`). This means `batch_end` is
  slightly delayed — documented as "measures time the consumer held
  the batch."
- **Epoch propagation via ContextVar.** Avoids coupling the loader
  to the trainer. Any caller that wants epoch-aware events can set
  the ContextVar; default is `None`.
- **No new env vars** — respect the existing observer registry.

## Success criteria

- `uv run pytest tests/data/test_loader.py tests/train/test_trainer.py -v`
  passes.
- `uv run ruff check operad/data/loader.py operad/runtime/events.py
  operad/train/trainer.py` clean.
- Old NDJSON traces (no batch events) still replay cleanly in the
  dashboard.
