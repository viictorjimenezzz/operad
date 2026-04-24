# 4-2 — LR schedulers

**Wave.** 4 (depends on 3-2).
**Parallel with.** 4-1, 4-3.
**Unblocks.** 5-1 (full training demo).

## Context

"Learning rate" in operad is the knob the rewriter reads to decide
how aggressively to edit a parameter. Low LR → minimal edits; high
LR → wholesale rewrite. `lr_scheduler` ports the standard PyTorch
scheduler zoo and lets the user anneal exploration over an epoch
budget.

Read `.context/NEXT_ITERATION.md` §8 and the PyTorch
`torch.optim.lr_scheduler` docs for the naming conventions we match.

## Scope — in

### `operad/optim/lr_scheduler.py`

- Base class:
  - `class LRScheduler(ABC)`:
    - Constructor: `optimizer: Optimizer, last_epoch: int = -1`.
    - `get_lr(self) -> list[float]` — abstract; one LR per param group.
    - `step(self)` — advance `last_epoch`; compute new LRs; write
      back into `optimizer.param_groups[i].lr`.
    - `state_dict(self) / load_state_dict(sd)` — round-trip `last_epoch`
      and any history.
    - Store `base_lrs: list[float]` captured at construction so
      schedulers can compute relative to base.
- Concrete schedulers (one small class each):
  - `ConstantLR(optimizer)` — never changes.
  - `StepLR(optimizer, step_size: int, gamma: float = 0.5)` — shrink
    by `gamma` every `step_size` epochs.
  - `MultiStepLR(optimizer, milestones: list[int], gamma: float = 0.5)` —
    explicit milestones.
  - `ExponentialLR(optimizer, gamma: float)` — multiply every step.
  - `CosineExplorationLR(optimizer, T_max: int, eta_min: float = 0.0)`
    — cosine anneal from base to `eta_min` over `T_max` epochs.
  - `WarmupLR(optimizer, warmup_epochs: int, final_lr: float)` — ramp
    up from 0 to base over `warmup_epochs`, then constant.
  - `ReduceLROnPlateau(optimizer, mode: Literal["min", "max"],
    factor: float = 0.5, patience: int = 2, threshold: float = 1e-4)`
    — takes an external metric at `step(metric_value)`.
- Utility:
  - `class ChainedScheduler(list[LRScheduler])` — step multiple
    schedulers in sequence.
  - `class SequentialLR(optimizer, schedulers: list[LRScheduler],
    milestones: list[int])` — switch between schedulers at
    milestones.

### `operad/optim/__init__.py`

Export every scheduler + `LRScheduler` base.

### `tests/optim/test_lr_scheduler.py`

- Each scheduler produces expected LRs over a 10-epoch schedule:
  - `StepLR(step=3, gamma=0.5)`: `[lr, lr, lr, lr/2, lr/2, lr/2, lr/4, ...]`.
  - `CosineExplorationLR(T_max=10)`: endpoint LRs are base and eta_min.
  - `WarmupLR(warmup_epochs=3)`: LRs monotonically increase over 3 epochs.
  - `ReduceLROnPlateau`: stagnating metric eventually triggers LR decay.
- `state_dict` / `load_state_dict` round-trip.
- `ChainedScheduler` applies all children per step.
- Per-param-group independence: a two-group optimizer sees both
  groups' LRs scale under one scheduler.

## Scope — out

- Do **not** modify `Optimizer` or rewriters. Schedulers read and
  write `optimizer.param_groups[i].lr`; they are otherwise inert.
- Do not integrate with `Trainer` — `Trainer` will call
  `scheduler.step()` itself in 4-3.
- Do not introduce a per-parameter LR (only per-group, matching
  PyTorch).

## Dependencies

- 3-2: `Optimizer`, `ParamGroup`.

## Design notes

- **LR semantics in operad.** Unlike PyTorch, our LR is unbounded
  and enters a prompt. A value of `1.0` means "rewrite from scratch
  as guided by the gradient"; `0.0` means "do nothing." Typical
  schedules stay in `[0.1, 1.0]`. Rewriters in 2-3 should be robust
  to `lr` outside this range and clamp internally, but document the
  typical band.
- **No optimizer mutation.** Schedulers *read* optimizer group count
  at construction and *write* `lr` on `step()`. No other state is
  touched.
- **Epoch-based, not step-based.** `step()` in our world is called
  once per epoch (as in PyTorch's default); callers who want batch-
  step cadence can call it per batch at their own risk.

## Success criteria

- `uv run pytest tests/optim/test_lr_scheduler.py` passes offline.
- `uv run ruff check operad/optim/lr_scheduler.py` clean.
- `from operad.optim.lr_scheduler import StepLR, CosineExplorationLR,
  ReduceLROnPlateau, ...` works.
- No edits outside `operad/optim/` and `tests/optim/`.
