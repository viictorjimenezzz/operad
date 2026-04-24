# 1-4 — `Agent.auto_tune(kind=...)` dispatcher

**Wave.** 1. **Parallel with.** 1-{1,2,3,5,6}.

## Context

`Agent.auto_tune(dataset, metric, ...)` today always spins up an
`EvoGradient`. That's the right default, but users who want
`TextualGradientDescent`, `MomentumTextGrad`, `OPROOptimizer`, or
`APEOptimizer` have no one-liner. Add a `kind` keyword that
dispatches to the full fleet.

## Scope — in

### `operad/core/agent.py`

Extend `Agent.auto_tune` signature:

```python
async def auto_tune(
    self,
    dataset,
    metric,
    *,
    kind: Literal["evo", "textgrad", "momentum", "opro", "ape"] = "evo",
    mutations: list[Op] | None = None,        # evo only
    population_size: int = 8,                  # evo / ape only
    generations: int = 4,                      # evo only
    epochs: int = 1,                           # textgrad / momentum only
    lr: float = 1.0,                           # textgrad / momentum only
    rng = None,
    **kwargs: Any,                             # forward-compat
) -> Agent:
```

Internal dispatch:

- `kind="evo"` (current behavior) — clone, `EvoGradient`, run.
- `kind="textgrad"` — mark_trainable(role+task+rules), build
  `TextualGradientDescent`, wrap in a minimal `Trainer`, call
  `fit(DataLoader(dataset), epochs=epochs)`, return the trained agent.
- `kind="momentum"` — same but `MomentumTextGrad`.
- `kind="opro"` / `kind="ape"` — similar, plus wire the
  `evaluator` closure they need (score a candidate value by running
  the agent on one batch).

Each branch is ~20 LOC; extract helpers but keep them in the same file.

### Tests

`tests/core/test_auto_tune_kinds.py`:

- For each `kind` value, `auto_tune` returns an `Agent` whose
  `hash_content` differs from the seed (with a FakeLeaf + stubbed
  rewriters/critics, all deterministic).
- Unknown `kind` raises `ValueError` with a clear message naming
  the allowed values.
- `mutations=None` triggers `default_mutations(self)` for `evo`; for
  other kinds the parameter is ignored (not an error).

## Scope — out

- Do not change existing `auto_tune(kind="evo")` default behavior.
- Do not add new optimizer kinds. This is dispatch, not invention.
- Do not modify the optimizer classes themselves.

## Dependencies

- `operad.optim.{EvoGradient, TextualGradientDescent,
  MomentumTextGrad, OPROOptimizer, APEOptimizer}` (all existing).
- `operad.train.Trainer` (existing).
- `operad.data.DataLoader` (existing).

## Design notes

- **`kind` default stays `"evo"`.** Backward compat. No one's old
  code breaks.
- **Trainer wrapping for non-evo kinds.** Use a minimal loss
  (`LossFromMetric(metric)`) so users don't need to provide a
  `Loss` explicitly. Document that passing a richer loss via
  `**kwargs` (e.g., `loss=CriticLoss(my_critic)`) overrides the
  default.
- **Evaluator closure for OPRO/APE.** Compose from: clone agent,
  apply candidate value to one parameter, build, evaluate on first
  few batch items, return metric score. Keep it O(1 LLM call per
  candidate per batch).
- **Do not mutate `self`.** Every `kind` branch works on `self.clone()`
  — same invariant the current `evo` branch already holds.
- **`auto_tune_async_generator`** would be nice (yielding
  per-generation snapshots for live UI) — flag as follow-up, not in
  this slot.

## Success criteria

- `tests/core/test_auto_tune_kinds.py` passes for all 5 kinds
  offline.
- `uv run ruff check operad/core/agent.py` clean.
- Existing `auto_tune` tests still pass (default `kind="evo"`
  behavior unchanged).
- Docstring lists all supported kinds with a one-line description.
