# 3-1 — `backward()` propagation algorithm

**Wave.** 3 (depends on 2-1, 2-2, 2-4, 2-5).
**Parallel with.** 3-2.
**Unblocks.** 4-3 (`Trainer`).

## Context

With the tape recording the forward pass, and `Loss` / `BackpropAgent`
/ `ParameterGradAgent` in place, we can write the reverse walk:
propagate a loss's `TextualGradient` upstream through the tape,
populating `.grad` on every trainable `Parameter`.

This is the heart of the framework. Read
`.context/NEXT_ITERATION.md` §6 carefully; the algorithm there is
the spec.

## Scope — in

### `operad/optim/backward.py`

- Entry point:
  - `async def backward(tape: Tape, loss: TextualGradient, *,
    propagator_factory: Callable[[], BackpropAgent] | None = None,
    parameter_grad_factory: Callable[[ParameterKind], ParameterGradAgent]
    | None = None,
    concurrency: int = 4) -> None`.
  - Also expose as `Tape.backward(loss, ...)` by attaching the
    method onto `Tape` at import time (or in `Tape` itself if 2-5
    left room for it).
- Algorithm (walk entries in reverse):
  1. Seed `downstream_grad[root_path] = loss`.
  2. For each `entry` in `tape.entries_in_reverse()`:
     a. `grad_out = downstream_grad.get(entry.agent_path, null)`.
     b. If `grad_out.severity == 0`, skip (null-gradient
        short-circuit).
     c. For a **leaf** entry: compute per-parameter gradients via
        `parameter_grad(...)` for every trainable `Parameter` on
        `entry.agent_ref()`; write `param.grad` in place.
     d. For a **composite** entry (Pipeline / Parallel / Switch /
        other): call `propagate(...)` to get an output-gradient for
        this node, then split it into per-child contributions and
        record in `downstream_grad[child_path] = ...`.
  3. Apply registered backward hooks on each agent as grads are
     computed (use `Agent._backward_hooks` from 2-1).
- Structural split rules (implement as small functions on the side
  of the main loop, selected by the composite's *class name* or by
  a new `ComposeKind` enum in `operad.optim.backward`):
  - **Pipeline**: the gradient at stage *i*'s output equals the
    gradient propagated upstream from stage *i+1*'s input. Walk
    children in reverse Pipeline order.
  - **Parallel**: same gradient fan-out to every child (or weighted
    by `combine` if `combine` exposes per-key weights). Document
    the default as "uniform fan-out" and leave weighted for a future
    task.
  - **Switch**: only the taken branch gets the full gradient; other
    branches get the null gradient. Discover the "taken branch" by
    matching `entry.output` against each child entry's output.
  - **Debate**: TBD — if 2-5 captures enough state, fan-out
    uniformly for now. Document the limitation.
  - **Generic composite** (user-defined `forward`): fall back to
    "propagate to every child in the tape with the same grad" — a
    safe default. Emit a one-time warning when this path is hit, so
    users know they may want a custom rule.
- Registration hook for custom split rules:
  - `register_backward_rule(composite_cls: type[Agent],
    fn: Callable[[TapeEntry, TextualGradient, list[TapeEntry]],
    dict[str, TextualGradient]]) -> None`.
  - Keeps a module-level registry so new composite types can plug
    in their own rule without editing this module.
- Concurrency:
  - Where independent (e.g., Parallel children, or separate leaves
    in one Pipeline stage), dispatch `parameter_grad` calls via
    `asyncio.gather` bounded by `concurrency`.

### `operad/optim/__init__.py`

Export `backward`, `register_backward_rule`.

### `tests/optim/test_backward.py`

- **Leaf**: stub `ParameterGradAgent`s to return deterministic
  gradients; assert every trainable parameter on the leaf has
  `.grad` populated.
- **Pipeline**: stub both `BackpropAgent` and `ParameterGradAgent`.
  Run `backward` on a 3-stage pipeline tape; assert that each stage
  received a gradient and each stage's trainable params got
  per-parameter gradients. Reverse-order propagation is exercised.
- **Parallel**: fan-out — each branch's params get the same
  gradient (in terms of the stubbed propagator returning a constant).
- **Switch**: only the taken branch's params have grads; the untaken
  branch has `.grad is None`.
- **Null gradient short-circuit**: if the loss returns
  `TextualGradient(severity=0.0)`, every `.grad` remains `None`.
- **Hooks**: `register_backward_hook(fn)` on a specific leaf fires
  with the gradient during backward.
- **Custom rule**: register a custom rule for a user composite; assert
  the custom split is used.
- **Error path**: if a propagator raises, `backward` surfaces the
  error with a clear message naming the node path.
- **Determinism**: two backward runs on the same tape + same stubs
  produce identical `.grad` payloads (important for cassette replay).

## Scope — out

- Do **not** implement `Optimizer.step()` — that is 3-2.
- Do not write the full fit loop — that is 4-3.
- Do not modify `operad/optim/tape.py` unless you choose to attach
  `backward` there (clearly document the decision in the PR).
- Do not implement gradient aggregation across multiple batches —
  that lives in 4-3 (`Trainer` accumulation).

## Dependencies

- 2-5: `Tape`, `TapeEntry`, `tape()`.
- 2-4: `BackpropAgent`, `ParameterGradAgent`, `propagate`,
  `parameter_grad`, `PARAMETER_GRAD_AGENTS`.
- 2-2: `Loss` (only via `TextualGradient`, not directly).
- 2-1: `Agent.parameters()`, `Agent._backward_hooks`.
- 1-1: `Parameter`, `TextualGradient`.

## Design notes

- **Walk order.** Strict reverse tape order. Do not try to
  reconstruct the static `AgentGraph` — the runtime tape is the
  source of truth (static graph may have been traced with sentinels
  that chose a different branch). Entry identity over path identity.
- **`downstream_grad` keying.** Map by `agent_path`, not by agent
  identity — because a single `Agent` instance could be re-used in
  multiple tree slots.
- **Composite classification.** Do not hard-code `isinstance(entry_agent,
  Pipeline)` with string imports; use `type(agent).__mro__` walked
  against the registry of backward rules. Fallback rule = generic
  composite.
- **No graph-static computation.** Do not try to do anything the
  tape can't support. This is a *runtime* backward; if the user
  passed `no_grad()`, the tape is empty, and `backward` is a no-op
  with a clear warning.
- **Observability.** Emit an `AgentEvent(kind="end", ...)` with a
  synthetic path like `"_backward.<node_path>"` when a propagator
  / param-grad agent finishes, so `JsonlObserver` sees the backward
  pass too. This makes training runs debuggable.

## Success criteria

- `uv run pytest tests/optim/test_backward.py` passes offline with
  stubs.
- `uv run ruff check operad/optim/backward.py` is clean.
- After `await backward(tape, loss)`, every trainable parameter in
  the tree has `.grad` populated (unless the loss was null).
- `register_backward_rule` actually affects the algorithm's output
  in the test for a custom rule.
- No edits outside `operad/optim/` and `tests/optim/`.
