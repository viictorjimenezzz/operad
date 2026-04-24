# 4-3 — `Trainer` + callbacks

**Wave.** 4 (depends on 1-2, 2-2, 3-1, 3-2).
**Parallel with.** 4-1, 4-2.
**Unblocks.** 5-1 (demo), 5-3 (freeze integration).

## Context

`operad.train.Trainer` is the PyTorch-Lightning analog: wraps the
agent, optimizer, loss, optional scheduler, and callbacks, and
exposes `fit()` / `evaluate()` / `predict()`. It's the user-facing
entry point.

Read `.context/NEXT_ITERATION.md` §9 and the existing
`operad/benchmark/evaluate.py` (pattern reuse).

## Scope — in

### `operad/train/__init__.py`

Re-exports `Trainer`, every callback class, `TrainingReport`.

### `operad/train/trainer.py`

- `class Trainer(Generic[In, Out])`:
  - Constructor:
    - `agent: Agent[In, Out]`
    - `optimizer: Optimizer`
    - `loss_fn: Loss`
    - `scheduler: LRScheduler | None = None`
    - `callbacks: list[Callback] = []`
    - `metrics: list[Metric] = []` — for validation reporting,
      not loss. `Trainer` always logs `loss_fn` + every metric on
      val epochs.
    - `max_grad_norm: float | None = None` — textual-gradient
      clipping (cap severity; see design notes).
    - `accumulation_steps: int = 1`
  - Public async methods:
    - `async def fit(self, loader: DataLoader, val_ds: Dataset |
      None = None, *, epochs: int, early_stopping: EarlyStoppingSpec |
      None = None) -> TrainingReport`
    - `async def evaluate(self, ds: Dataset) -> EvalReport`
    - `async def predict(self, x: In) -> OperadOutput[Out]`
  - Internal:
    - `_run_batch(batch: Batch) -> BatchResult` (forward-under-tape,
      loss, backward, optional step-every-N).
    - `_run_val_epoch(ds: Dataset) -> EvalReport`.
    - Hook fan-out: each of (`on_fit_start`, `on_epoch_start`,
      `on_batch_start`, `on_batch_end`, `on_epoch_end`, `on_fit_end`,
      `on_validation_end`) iterates `callbacks` in order.
  - Compose with OPRO/APE optimizers: if the optimizer exposes a
    `.needs_evaluator` attribute equal to `True`, `Trainer` passes
    a closure `evaluator(param, value) -> float` that runs a quick
    single-batch evaluation. Wired here, not in the optimizer.

### `operad/train/report.py`

- `class EpochReport(BaseModel)`:
  - `epoch: int`
  - `train_loss: float`
  - `train_metrics: dict[str, float]`
  - `val_loss: float | None`
  - `val_metrics: dict[str, float]`
  - `lr: list[float]` — per-param-group
  - `duration_s: float`
  - `hash_content: str` — agent state hash at end of epoch
- `class TrainingReport(BaseModel)`:
  - `epochs: list[EpochReport]`
  - `best_epoch: int`
  - `best_val_metric: float`
  - `best_hash_content: str`
  - `seed_hash_content: str`

### `operad/train/callbacks.py`

- `class Callback(Protocol)`:
  - Optional methods (empty by default): `on_fit_start`,
    `on_epoch_start`, `on_batch_start`, `on_batch_end`,
    `on_epoch_end`, `on_validation_end`, `on_fit_end`.
- Concrete:
  - `EarlyStopping(monitor: str = "val_loss", mode: Literal["min",
    "max"] = "min", patience: int = 3, min_delta: float = 1e-4)`.
  - `BestCheckpoint(path: str | Path, monitor: str = "val_loss",
    mode: Literal["min", "max"] = "min")` — uses existing `freeze()`
    to persist the current agent state on improvement.
  - `GradClip(max_severity: float = 0.5)` — called in
    `on_batch_end` after `backward()` and before `optimizer.step()`;
    clips `param.grad.severity` in place.
  - `PromptDrift(max_hash_changes: int = 5)` — monitors
    `hash_content` delta across epochs and issues a warning if
    changes exceed threshold.
  - `LearningRateLogger` — logs per-epoch LRs.
  - `MemoryRotation(max_tape_entries: int = 10_000)` — if a tape
    gets too big, skip recording until next batch (soft guardrail).

### `tests/train/test_trainer.py`

- End-to-end offline fit loop with `FakeLeaf`, stubbed optimizer
  (override `step`), stubbed loss. Confirm:
  - `fit()` runs the right number of epochs.
  - Callbacks are called in the declared order.
  - `TrainingReport` tracks `hash_content` deltas.
  - Validation is run when `val_ds` is supplied.
  - `EarlyStopping` halts after patience epochs of no improvement.
  - `BestCheckpoint` writes a file on improvement (check the file
    exists and contains the expected frozen state).
  - `GradClip` actually clips severities > threshold.
  - `accumulation_steps=4`: `optimizer.step()` is called every 4
    batches, not every batch.
  - `max_grad_norm=0.3`: `GradClip` is applied by default when this
    is set.

## Scope — out

- Do **not** implement new metrics / losses / optimizers — wave 4-1
  handles the fleet, 3-2 handles SGD.
- Do not modify `operad/benchmark/evaluate.py` (reuse via import).
- Do not change `operad/core/`. `state_dict` alias is 5-3, not here.

## Dependencies

- 1-2: `DataLoader`, `Batch`, `random_split`.
- 2-2: `Loss`.
- 2-5: `tape()` context.
- 3-1: `backward()`.
- 3-2: `Optimizer`.
- 4-2 (optional): `LRScheduler` protocol.
- `operad.benchmark.{Dataset, evaluate, EvalReport}` (existing).
- `operad.core.freeze` (existing) — for `BestCheckpoint`.

## Design notes

- **Tape hygiene.** Each batch opens its own `tape()`; after
  `backward()` + `optimizer.step()`, the tape is GC'd. Do not retain
  tapes across batches (memory leak).
- **Gradient accumulation.** `zero_grad()` is only called every N
  batches; `backward()` is called every batch and grads accumulate
  (rewriters should treat multiple grads on the same parameter as
  a new latest; `Momentum` folds into its summary). Document
  explicitly what "accumulate" means for textual gradients — in the
  simplest implementation, the N grads are concatenated into one
  when step() fires. Pick one clear semantics and document.
- **Deterministic runs.** If every source of randomness is seeded
  (DataLoader seed, optimizer RNG, rewriter seed), the whole run is
  reproducible against a cassette. This is the hook that 5-5 will
  validate.
- **`evaluate()` is straight delegation** to the existing
  `operad.benchmark.evaluate`. Add a thin wrapper so the method
  shape matches `fit()`'s return-type style.
- **No hidden progress bars / printing.** Users who want a live TUI
  add `RichDashboardObserver` from the existing observer stack;
  `Trainer` stays quiet by default.
- **Callback ordering.** Early callbacks' `on_*_end` fire first
  (PyTorch-Lightning convention), so `BestCheckpoint` placed before
  `EarlyStopping` will checkpoint before stopping.

## Success criteria

- `uv run pytest tests/train/` passes offline.
- `uv run ruff check operad/train/` clean.
- `from operad.train import Trainer, EarlyStopping, BestCheckpoint,
  GradClip, TrainingReport` works.
- Wave 5-1 demo can import and use `Trainer` to train a `FakeLeaf`
  pipeline to higher score on a toy metric.
- Zero edits outside `operad/train/` and `tests/train/`.
