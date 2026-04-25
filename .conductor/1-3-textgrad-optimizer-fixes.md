# Tighten textual-gradient optimizer correctness (Momentum / OPRO / APE)

## Goal
Three concrete bugs in the optimizer fleet cause silent training failures. Fix all three as one cohesive task; the changes are small and the optimizers must stay behaviorally aligned with `TextualGradientDescent`.

## Context

1. **`MomentumTextGrad` does not decay the current step.** `operad/optim/momentum.py:152-162` decays existing history entries by `momentum` then appends the fresh `grad` at full severity. With `momentum=0.5` users expect `[0.25*g₀, 0.5*g₁, 1.0*g₂]` to become `[0.25*g₀, 0.5*g₁, 0.5*g₂]` (or the equivalent Polyak/Nesterov shape). Today the most recent step always dominates the summarizer.

2. **`OPROOptimizer` silently consumes retries on coerced candidates.** `operad/optim/opro.py:207-223` raises `ValueError("candidate coerced by constraint")` and continues the retry loop. After `max_retries` it exits without updating the parameter. No warning, no fallback to `apply_rewrite`-style accept-coerced semantics.

3. **`APEOptimizer` silently skips coerced candidates.** `operad/optim/ape.py:184-192` uses `continue` on coercion. If all `k` candidates coerce, `parsed_candidates` is empty and the parameter is silently never updated.

`TextualGradientDescent` (`operad/optim/sgd.py` → `apply_rewrite`) handles coercion correctly via a tightened-prompt retry: that's the reference behavior to align with.

## Scope

**In scope:**
- `operad/optim/momentum.py` — decay the current grad consistently (or document a deliberate "Polyak-style" deviation if you choose to keep current semantics).
- `operad/optim/opro.py` — accept coerced candidates (mirror `apply_rewrite`) or, on exhausted retries, fall back to the best-scored coerced candidate; emit a warning either way.
- `operad/optim/ape.py` — same treatment; if all coerced, accept the best scored coerced candidate and warn.
- Tests under `tests/optim/` that pin each fix with a fake constraint that always coerces.

**Out of scope:**
- `operad/optim/sgd.py` (already correct) — you may read it, do not modify.
- `operad/optim/evo.py` — separate code path, not on this list.
- Schema-aware retry hint inside `RewriteAgent` (separate task: 1-6).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/optim/rewrite.py`, `operad/optim/parameter.py`, `operad/optim/backward.py`, `operad/train/*`, `operad/runtime/*`, `operad/utils/*`, `operad/core/*`.

## Implementation hints
- For momentum: investigate Polyak vs Nesterov-style averaging in the textual-gradient setting — what does the TextGrad paper recommend? Decide and document. The simplest correct fix is: scale `grad.severity *= decay` before appending so that on the *next* step the just-added entry decays to `decay`, the previous to `decay²`, etc.
- For OPRO/APE: the accept-coerced path already exists in `apply_rewrite` — extract and reuse if you want, but a literal copy is fine since these optimizers are intentionally distinct.
- Add a `warnings.warn(...)` (UserWarning) on the silent-failure paths — users should know when the optimizer gave up.

## Acceptance
- Three regression tests, one per bug, each pinning the fixed behavior.
- All optimizers still pass their existing tests.
- A short note in each optimizer's docstring describing how it handles coerced candidates.
