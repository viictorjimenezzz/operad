# 2-1 — Agent surface: `parameters()`, hooks, `no_grad()`

**Wave.** 2 (depends on 1-1).
**Parallel with.** 2-2, 2-3, 2-4, 2-5.
**Unblocks.** 3-1 (`backward()`), 3-2 (`Optimizer`), 4-3 (`Trainer`).

## Context

This is the *one* wave-2 task that modifies `operad/core/agent.py`.
Every other wave-2 slot works inside `operad/optim/`. Keep the edits
here surgical so those slots' agents see a stable `Agent` class.

We need to give `Agent` a PyTorch-muscle-memory surface for iteration
over trainable state, per-agent hooks, and a gradient-disabling
context manager.

Read `operad/core/agent.py` (entire file) and
`.context/NEXT_ITERATION.md` §3, §10 before starting.

## Scope — in

### `operad/core/agent.py`

Add methods on `Agent`:

- `parameters(self, *, recurse: bool = True) -> Iterator[Parameter]`
  yields every `Parameter` in the (sub-)tree.
- `named_parameters(self, *, recurse: bool = True) -> Iterator[tuple[str, Parameter]]`
  yields `(dotted_path, parameter)` pairs.
- `trainable_parameters(self) -> Iterator[Parameter]` — filter
  `requires_grad`.
- `mark_trainable(self, *, role=False, task=False, rules=False,
  examples=False, temperature=False, top_p=False, recurse=True,
  **per_path: bool) -> None` — toggles `requires_grad` across the
  tree; `per_path` allows `reasoner.role=True` etc.
- A matching `freeze_parameters(...)` / `unfreeze_parameters(...)`
  that set `requires_grad` accordingly (PyTorch's
  `for p in m.parameters(): p.requires_grad = False` idiom).

Hooks:

- `register_forward_pre_hook(self, fn) -> Handle` — `fn(agent, input)`
  runs before `forward`; its return (if not None) *replaces* input.
- `register_forward_hook(self, fn) -> Handle` — `fn(agent, input, output)`
  runs after `forward`; return value ignored.
- `register_backward_hook(self, fn) -> Handle` — `fn(agent, grad)`
  runs during `tape.backward()` (the wave-3 piece will call this).
- `Handle.remove()` unregisters; double-remove is a no-op.

The three hook lists live as private instance lists
(`_forward_pre_hooks`, `_forward_hooks`, `_backward_hooks`). They are
*not* persisted by `state()` / serialized by `freeze()` — hooks are
runtime-only.

### `operad/optim/context.py` (new file)

Two async context managers sharing a `ContextVar`:

- `async def no_grad()` — disables tape recording for the duration.
- `async def inference_mode()` — stricter: also disables hooks. (Mirror
  PyTorch's distinction.)

Implementation: a `ContextVar[bool] _GRAD_ENABLED` defaulting to
`True`. `tape()` (wave-2 slot 2-5) checks it before recording;
`Agent.invoke` checks it before running hooks.

Export from `operad/optim/__init__.py`.

### `operad/core/agent.py`, in `invoke` (or equivalent)

- Call `_forward_pre_hooks` before `forward`, allow them to rewrite
  `x`.
- After `forward`, call `_forward_hooks`.
- `_backward_hooks` are *not* called here; they are invoked during
  `tape.backward()` in wave 3-1.
- Gate hook execution on `inference_mode()` — if set, skip.

### Tests

- `tests/core/test_agent_parameters.py`
  - A `FakeLeaf` with `role`, `task`, `rules`, `examples`, `config`
    yields the expected `Parameter` set.
  - `parameters(recurse=False)` returns only direct params.
  - A composite with two children yields its own params plus both
    children's; `named_parameters()` prefixes paths properly.
  - `mark_trainable(role=True, task=False)` flips `requires_grad`
    accordingly.
  - `mark_trainable` with a dotted path (`"child.role": True`) only
    flips that specific parameter.
- `tests/core/test_agent_hooks.py`
  - `register_forward_pre_hook` can mutate input.
  - `register_forward_hook` sees the output.
  - `handle.remove()` stops the hook firing.
  - Multiple hooks fire in registration order.
  - `inference_mode()` skips hooks entirely.
- `tests/optim/test_context.py`
  - `no_grad()` disables `_GRAD_ENABLED`; `inference_mode()` does too
    plus gates hooks.
  - Nested `no_grad()` restores the outer state on exit.

## Scope — out

- Do **not** add a tape or backward pass — that is wave 2-5 and 3-1.
- Do not implement `Optimizer.step()`, `Loss.compute()`, rewrite
  agents, or backprop agents.
- Do not touch `operad/benchmark/`, `operad/algorithms/`, or
  `operad/agents/`.
- Do not modify `Agent.forward` logic — just add the hook call sites
  around it.

## Dependencies

- Wave 1-1: `operad.optim.parameter.Parameter` + subclasses +
  `ParameterKind`.

## Design notes

- **Discovery of parameters.** `parameters()` has to read from the
  declared state (role, task, rules, examples, config). Centralize
  the logic in a single helper (`_iter_declared_parameters`) so
  wave-5 additions (e.g., `Parameter` on renderer, on a new field)
  are easy.
- **List-valued params.** `rules` and `examples` can be viewed two
  ways: as a *single* `RuleListParameter` whose `value` is the whole
  list, or as N `rule_i` params each viewing one element. Default
  behaviour of `parameters()`: yield the list-valued param *only*.
  Provide an opt-in flag `parameters(element_wise=True)` that yields
  per-element parameters instead. The optimizer chooses which.
- **Hooks and symbolic tracing.** `build()`'s symbolic tracer must
  bypass hooks (they might not tolerate sentinel inputs). In
  `invoke`, check `_TRACER.get()` — if set, skip hooks. (This is
  consistent with the existing bypass of validation during tracing.)
- **Weak references in Parameter.** `Parameter.attach(agent)` uses
  `weakref.ref` to avoid keeping a dead agent alive. Document this.
- **No hook persistence.** Do not pickle hooks in `state()`. Leave a
  comment noting this.

## Success criteria

- `uv run pytest tests/core/test_agent_parameters.py tests/core/test_agent_hooks.py
  tests/optim/test_context.py` passes.
- All existing tests still pass (`uv run pytest tests/`).
- `uv run ruff check operad/core/agent.py operad/optim/context.py`
  is clean.
- Parallel wave-2 tasks (2-2..2-5) are unaffected — they don't touch
  `operad/core/agent.py`.
