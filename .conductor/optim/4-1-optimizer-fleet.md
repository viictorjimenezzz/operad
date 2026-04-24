# 4-1 — Optimizer fleet: Momentum, Evo, OPRO, APE

**Wave.** 4 (depends on 3-2).
**Parallel with.** 4-2, 4-3.
**Unblocks.** Full comparison studies; 5-1 demo; 5-4 traceback.

## Context

With `Optimizer` + `TextualGradientDescent` landed, the fleet of
research-grade optimizers drops in as subclasses sharing the same
interface. Each is small (50-200 LOC) but has distinct semantics.

Read `.context/NEXT_ITERATION.md` §7.2-7.6,
`operad/algorithms/evolutionary.py` (for the port), and the original
papers (TextGrad / APE / OPRO — the citations live at the bottom of
the `operad/optim/README.md`).

## Scope — in

### `operad/optim/momentum.py` — `MomentumTextGrad`

- Accumulates a rolling summary of recent gradients for each
  parameter. The summary is produced by a small `GradSummarizer`
  agent: `Agent[MomentumInput, TextualGradient]`.
- State: `param.momentum_state["momentum"] = {"history": list[TextualGradient]}`.
- `step()`:
  1. For each trainable param with `.grad`, push `.grad` onto the
     history.
  2. Summarize history (keep last `k=5` entries by default) via
     the `GradSummarizer` agent.
  3. Pass the *summary* gradient to the rewriter (via
     `apply_rewrite`), not the raw latest gradient.
  4. Apply decay: `param.momentum_state["momentum"]["history"] =
     history[-k:]` with optional exponential decay on severity.
- Parameter-group knob: `momentum: float` (default 0.9) — the
  decay factor.

### `operad/optim/evo.py` — `EvoGradient`

- Re-casts `operad/algorithms/evolutionary.py` as an `Optimizer`.
- Constructor: `params, lr=1.0, mutations: list[Op], metric: Metric,
  dataset: list[tuple[In,Out]], population_size=8, rng=None`.
- State: `self._population: list[Agent]` cached across `step()`
  calls; `self._generation: int`.
- `step()`:
  1. If no population: seed by cloning the root agent and applying
     a random mutation `population_size` times.
  2. Build the whole population (asyncio.gather).
  3. Evaluate on `dataset` with `metric` (reuse
     `operad.benchmark.evaluate`).
  4. Sort by score; keep top half as survivors.
  5. Refill by cloning + random-mutating survivors.
  6. Write the best agent's declared state back to the optimizer's
     root parameters (via `Parameter.write`).
- Critical cross-cut: this optimizer mutates the whole agent tree,
  not just a single parameter. It bypasses the rewriter path and
  instead uses `Op.apply`. Document this clearly — it's a
  discrete-optimizer escape hatch, not a gradient-descent variant.
- **Deprecation of old `Evolutionary`.** Do *not* remove
  `operad/algorithms/evolutionary.py`. Import-shim it:
  `from operad.optim.evo import EvoGradient as Evolutionary` at
  the *bottom* of the file, mark the original class with a
  `DeprecationWarning` in its `__init__` pointing to
  `operad.optim.EvoGradient`. Keep behavior identical for one
  release cycle.

### `operad/optim/opro.py` — `OPROOptimizer`

- LLM-as-optimizer (Yang et al. 2023). For each parameter, maintain
  a history of `(value, metric_score)` pairs; at each step, show an
  `OPROAgent : Agent[OPROInput, OPROOutput]` the history and ask
  for a new candidate value.
- State: `param.momentum_state["opro"] = [(value, score), ...]`.
- `step()`:
  - Requires a metric signal, not just a gradient. The optimizer
    must be constructed with `objective_metric: Metric` and an
    evaluation callback `evaluator: Callable[[Parameter, T], Awaitable[float]]`
    that scores a candidate value. Typically `evaluator` runs the
    full agent on a held-out batch; callers are expected to set it
    up. (`Trainer` will wire this automatically when the user
    chooses `OPROOptimizer`.)
  - For each trainable param:
    1. Render history (last `k=20` by default).
    2. Invoke `OPROAgent` to get a new candidate.
    3. Evaluate candidate.
    4. If new score beats the history best, accept; else either
       retry (k≤3) or keep current.

### `operad/optim/ape.py` — `APEOptimizer`

- Sample-and-rank (Zhou et al. 2022). For each trainable param:
  1. Generate `K` candidate values via a `CandidateGenerator`
     `Agent` (or reuse the rewriter with varied seed / temperature).
  2. Evaluate each candidate with a user-supplied `evaluator`
     (same shape as OPRO's).
  3. Adopt the best.
- State: only final scores of current iteration; no long-term
  history.
- Distinguishing trait: pure BestOfN over the parameter space,
  ignores `.grad` entirely. Document this clearly — `.grad` is
  still populated by `backward()` but the optimizer just doesn't
  read it; a user combining APE with a `backward()`-only pipeline
  will get a warning (one-time, not per-step).

### `operad/optim/__init__.py`

Export `MomentumTextGrad`, `EvoGradient`, `OPROOptimizer`,
`APEOptimizer`, plus their input/output schema classes.

### Tests (one file per optimizer)

- `tests/optim/test_momentum.py` — confirm summary is produced (via
  stubbed `GradSummarizer`) and passed to rewriter.
- `tests/optim/test_evo.py` — population-based convergence on a toy
  metric (identical to the existing `Evolutionary` test semantics);
  confirm the best agent's state is written back to the root.
- `tests/optim/test_opro.py` — stubbed `OPROAgent` + stubbed
  evaluator; confirm history grows, best candidate accepted.
- `tests/optim/test_ape.py` — stubbed candidate generator +
  evaluator; confirm best of K is adopted.

## Scope — out

- Do **not** modify `operad/algorithms/evolutionary.py` beyond
  adding the deprecation warning + import shim. Behavior must not
  change.
- Do not implement `Trainer` wiring (4-3 handles evaluator
  injection for OPRO/APE).
- Do not add LR scheduler coupling — keep each optimizer standalone.

## Dependencies

- 3-2: `Optimizer`, `ParamGroup`, `TextualGradientDescent` (for
  subclass inheritance).
- 2-3: `apply_rewrite`, `rewriter_for`.
- 1-1: `Parameter`, `TextualGradient`.
- `operad.utils.ops` (existing) for `EvoGradient`.
- `operad.benchmark.evaluate` (existing) for `EvoGradient`'s fitness.
- `operad.metrics.base.Metric` (existing).

## Design notes

- **Each file under 200 LOC if possible.** If it grows longer, the
  optimizer's design is probably wrong; take a second pass.
- **Keep prompts close to optimizers.** `MomentumTextGrad`'s
  `GradSummarizer` has a tailored prompt; `OPROOptimizer`'s
  `OPROAgent` has another. Each in its own file alongside the
  optimizer class.
- **No shared implicit state across optimizers.** They all keep
  their scratchpads under `param.momentum_state[<optimizer_name>]`
  to avoid collision.
- **EvoGradient is the odd one out.** It ignores `.grad`, mutates
  the whole tree, and overrides `step()` with a substantially
  different shape. Document this in the class docstring; a user
  picking `EvoGradient` opts out of the textual-gradient flow for
  its lifetime.

## Success criteria

- All four test files pass offline.
- `uv run ruff check operad/optim/{momentum,evo,opro,ape}.py` clean.
- `from operad.optim import MomentumTextGrad, EvoGradient,
  OPROOptimizer, APEOptimizer` works.
- The existing `Evolutionary` test in `tests/` still passes
  (deprecation shim path).
- No breakage in `operad/algorithms/`, `operad/agents/`, or
  `operad/core/`.
