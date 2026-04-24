# 3-2 — Optimizer base + `TextualGradientDescent`

**Wave.** 3 (depends on 1-1, 2-3).
**Parallel with.** 3-1.
**Unblocks.** 4-1 (fleet), 4-2 (LR schedulers), 4-3 (`Trainer`).

## Context

With `Parameter` (1-1) and `RewriteAgent` (2-3) in place, we can
implement the `Optimizer` base class plus the default concrete
optimizer, `TextualGradientDescent`. Everything in wave 4 subclasses
from here.

Read `.context/NEXT_ITERATION.md` §7 and
`operad/optim/rewrite.py` (once 2-3 is merged) before starting.

## Scope — in

### `operad/optim/optimizer.py`

- `class Optimizer(ABC)`:
  - Constructor:
    - Accept either `list[Parameter]` or `list[dict]` of parameter
      groups (each dict has `params: list[Parameter]` plus per-
      group overrides `lr`, `momentum`, `constraint_override`).
    - Mirror PyTorch's parameter-group API for muscle memory.
  - Attributes:
    - `param_groups: list[ParamGroup]` — `ParamGroup` is a small
      Pydantic/dataclass with `params`, `lr`, `momentum`, `extras`.
    - `defaults: dict[str, Any]` — constructor defaults.
    - `state: dict[str, dict]` — per-`Parameter.path` scratchpad
      (mirrors PyTorch `optimizer.state`).
  - Methods:
    - `zero_grad(self, *, set_to_none: bool = True)` — clear
      `.grad` on every parameter in every group.
    - `@abstractmethod async def step(self) -> None` — subclass hook.
    - `named_parameters(self) -> Iterator[tuple[str, Parameter]]`.
    - `add_param_group(self, group: dict)` — late add.
    - `state_dict(self) -> dict` / `load_state_dict(sd: dict)` —
      serialize optimizer state (for checkpoint/resume).
  - Hook points:
    - `async def _apply_param_update(self, param: Parameter, group:
      ParamGroup) -> None` — the place subclasses override to apply
      the update rule. Default implementation in `Optimizer` is
      abstract (subclasses must provide).
  - Shared concurrency helper:
    - `async def _apply_updates(self, items: list[tuple[Parameter,
      ParamGroup]]) -> None` — dispatches `_apply_param_update` via
      `asyncio.gather` with a subclass-tunable `max_concurrent_updates`
      attribute (default 4).

### `operad/optim/sgd.py`

- `class TextualGradientDescent(Optimizer)`:
  - Constructor:
    - `params`, `lr=1.0`, `rewriter_factory: Callable[[ParameterKind],
      RewriteAgent]` (default = `operad.optim.rewrite.rewriter_for`
      instantiated with a default `Configuration`).
    - Accept a single global `Configuration` for rewriters or per-
      group overrides via param-group dicts.
  - `async def step(self):`
    - For each group, for each parameter with `requires_grad=True`
      and `.grad is not None and .grad.severity > 0`:
      1. Get the rewriter for `param.kind` (per-group override if
         any; else group-level; else factory default).
      2. `await apply_rewrite(param, param.grad, rewriter, lr=group.lr)`.
      3. Clear `param.grad` after applying (unless
         `persist_grads=True`).
    - Returns nothing.
  - `async def step` is idempotent on a zeroed gradient (no-ops).

### `operad/optim/__init__.py`

Export `Optimizer`, `ParamGroup`, `TextualGradientDescent`.

### `tests/optim/test_optimizer.py`

- `Optimizer(params, lr=0.5)` normalizes to a single param_group
  with `lr=0.5`.
- Param groups: `Optimizer([{"params":..., "lr": 2.0}, {"params":...,
  "lr": 0.3}])` — each group gets its own `lr`.
- `zero_grad()` clears `.grad` across all groups.
- `state_dict` / `load_state_dict` round-trip.
- `add_param_group` late-adds a group.

### `tests/optim/test_sgd.py`

- With a stubbed `RewriteAgent` (from 2-3, override `forward`),
  `optimizer.step()` mutates every trainable parameter's value.
- `.grad is None` after step by default.
- `persist_grads=True` preserves `.grad`.
- No updates occur when `requires_grad=False`.
- No updates occur when `param.grad.severity == 0`.
- Per-group `lr` is threaded into the rewriter call.
- Concurrency: stub rewriter with `asyncio.sleep(0.1)` and confirm
  10 params in one group take < 1s (i.e., they actually run in
  parallel). Set `max_concurrent_updates=2` and confirm the same
  10 take ≥ 0.5s.

## Scope — out

- Do **not** implement Momentum / Evo / OPRO / APE — 4-1.
- Do not implement LR schedulers — 4-2.
- Do not implement `Trainer` — 4-3.
- Do not modify `operad/optim/rewrite.py` — just consume it.

## Dependencies

- 1-1: `Parameter`, `ParameterKind`, `ParameterConstraint`.
- 2-3: `RewriteAgent`, `apply_rewrite`, `rewriter_for`.
- (Optional, for typing) 2-1: `Agent`.

## Design notes

- **Parameter group API.** Match PyTorch's exact shape:
  `Optimizer([{"params": [...], "lr": 1.0, "momentum": 0.9}])`. Dict
  keys override defaults. This is load-bearing for muscle memory.
- **State serialization.** `state_dict` should include the
  `momentum_state` of each param (which optimizer wrote into it
  during step()). Use `param.path` as the key — it survives
  clone() and is consistent across runs.
- **Rewriter reuse.** Rewriters are `Agent`s with `config`; do not
  rebuild them every step. Cache one rewriter instance per
  `(ParameterKind, Configuration)` tuple on the optimizer.
- **Error handling in step.** If one parameter's rewrite fails, the
  whole step must not silently swallow. Collect errors and raise
  after processing the others (so one bad param doesn't tank a
  100-param step). Use `ExceptionGroup` (Python 3.11+) or a
  custom `OptimizerStepError` that aggregates.
- **No blocking sleeps**, no thread pools; everything awaitable.

## Success criteria

- `uv run pytest tests/optim/test_optimizer.py tests/optim/test_sgd.py`
  passes offline with stubs.
- `uv run ruff check operad/optim/{optimizer,sgd}.py` is clean.
- `from operad.optim import Optimizer, TextualGradientDescent`
  works.
- After a full round — `tape → loss → backward → step` — a trainable
  parameter's `.value` in its underlying agent has changed
  (verifiable via `hash_content` delta).
- No edits outside `operad/optim/` and `tests/optim/`.
