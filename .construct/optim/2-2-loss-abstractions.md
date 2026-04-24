# 2-2 — Loss abstractions

**Wave.** 2 (depends on 1-1 for `TextualGradient`).
**Parallel with.** 2-1, 2-3, 2-4, 2-5.
**Unblocks.** 3-1 (`backward()`), 4-3 (`Trainer`).

## Context

A loss in operad is a `Metric` that *also* returns a `TextualGradient`
— it produces both the scalar score used for optimization and the
structured critique that seeds `backward()`.

The existing `Metric` protocol (in `operad/metrics/base.py`) already
returns a float. We extend it additively so every existing metric
can be lifted trivially, while LLM-judge losses (the existing
`Critic`) return rich gradients.

Read `operad/metrics/base.py`, `operad/metrics/rubric_critic.py`,
`operad/algorithms/judge.py`, and `.context/NEXT_ITERATION.md` §5.

## Scope — in

### `operad/optim/loss.py`

- `class Loss(Protocol)`:
  - `name: str`
  - `async def compute(self, predicted: BaseModel,
    expected: BaseModel | None) -> tuple[float, TextualGradient]: ...`
  - Concrete classes may also expose `score()` / `score_batch()` from
    the existing `Metric` protocol for backward compatibility — any
    `Loss` is-a `Metric` (higher-is-better score is the first element
    of the tuple).
- `class LossFromMetric(Loss)` — lift any `Metric` to a `Loss`:
  - Constructor takes a `Metric` and an optional
    `gradient_formatter: Callable[[BaseModel, BaseModel | None, float],
    str]` for the critique message (default: a templated
    "expected X, got Y, score=Z" string).
  - `compute` runs `metric.score` and wraps the result.
  - `severity = 1.0 - score` by default (score in [0,1]); expose a
    `severity_fn` hook for metrics with different ranges.
- `class CriticLoss(Loss)` — wrap a `Critic` (an
  `Agent[Candidate[In,Out], Score]`):
  - Constructor: `critic, name="critic_loss", severity_from: Literal["score","rationale"] = "score"`.
  - `compute` builds a `Candidate(input=None, output=predicted)`,
    invokes the critic, returns
    `(score.score, TextualGradient(message=score.rationale,
    severity=1.0 - score.score))`.
  - If the critic itself also populates `Score.deficiencies` (extend
    `Score` via a subclass if needed — but do not modify
    `operad/algorithms/judge.py`; instead let the critic's output
    type be any `BaseModel` that has `.score` and `.rationale`
    attributes, via duck typing).
- `class JSONShapeLoss(Loss)` — pure schema-driven loss:
  - Compare `predicted` field-by-field against the target schema's
    required fields. Missing or wrong-typed fields populate
    `by_field` with explicit messages.
  - Useful when the job is "make sure the answer parses."
- `class CompositeLoss(Loss)`:
  - Constructor: `losses: list[tuple[Loss, float]]` — (loss, weight).
  - `compute` runs each in parallel, aggregates floats as weighted
    sum, concatenates `TextualGradient.message` strings, merges
    `by_field` dicts. `severity` = weighted sum.
  - Delegate gradient routing: if a sub-loss hints `target_paths`,
    preserve them.

### `operad/optim/__init__.py`

Export `Loss`, `LossFromMetric`, `CriticLoss`, `JSONShapeLoss`,
`CompositeLoss`.

### `tests/optim/test_loss.py`

- `LossFromMetric(ExactMatch())` returns `(1.0, null_gradient())` on
  exact matches and `(0.0, TextualGradient(severity=1.0, ...))` on
  mismatches. Gradient message mentions expected/actual values.
- `CriticLoss` with a `FakeCritic` (stub that always returns
  `Score(score=0.7, rationale="close but…")`) produces
  `(0.7, TextualGradient(message="close but…", severity≈0.3))`.
- `JSONShapeLoss` flags missing required fields; `by_field`
  populated per field.
- `CompositeLoss([(l1, 0.7), (l2, 0.3)])` aggregates floats
  correctly; severity is weighted; concat message preserves order.
- A pure `Metric` passed where a `Loss` is expected should *not*
  pass `isinstance(…, Loss)` unless lifted.

## Scope — out

- Do **not** modify `operad/metrics/base.py` or any existing metric.
  If a metric needs a richer gradient, lift it via `LossFromMetric`.
- Do not add ranking / preference-based losses (RLHF-style
  pairwise). Those can come later as a sibling module.
- Do not modify `operad/algorithms/judge.py`. Duck-type on `.score`
  and `.rationale` instead.

## Dependencies

- Wave 1-1: `TextualGradient` (from `operad.optim.parameter`).
- `operad.metrics.base.Metric` (existing).
- `operad.algorithms.judge.Score`, `Candidate` (existing) — for type hints only.

## Design notes

- **Severity semantics.** `severity in [0, 1]` throughout. 0 = no
  update needed, 1 = totally wrong. Optimizers may multiply LR by
  severity to scale the update magnitude.
- **Null gradients.** When `score == 1.0` (or user-specified
  threshold), return `TextualGradient.null_gradient()` — the
  optimizer then skips that parameter entirely.
- **Async everywhere.** `compute` is always `async def` even for
  pure-Python losses. This keeps the `Trainer` loop uniform and lets
  `CompositeLoss` parallelize.
- **No silent float conversion.** If a metric produces a score
  outside [0, 1] (say `Rouge1` does), document the clamping or
  `severity_fn` used. Tests should cover both the normalized and
  the raw behavior.

## Success criteria

- `uv run pytest tests/optim/test_loss.py` passes offline with fake
  metrics and fake critics.
- `uv run ruff check operad/optim/loss.py` is clean.
- `from operad.optim import Loss, LossFromMetric, CriticLoss,
  JSONShapeLoss, CompositeLoss` works.
- No edits to `operad/metrics/`, `operad/algorithms/`, or
  `operad/core/`.
