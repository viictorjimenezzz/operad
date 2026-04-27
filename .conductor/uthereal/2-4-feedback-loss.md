# 2-4 — HumanFeedbackLoss

**Batch:** 2 · **Parallelizable with:** 2-1, 2-2, 2-3 · **Depends on:** 1-5

You are turning human feedback into an operad `TextualGradient` that the
optimizer can apply.

## Goal

Implement `HumanFeedbackLoss` as a `Loss`-protocol-compliant object.
Given the workflow's final answer (`pred`) and a `HumanFeedback`
(`expected`), return `(score, TextualGradient)` with the right
`target_paths`, `severity`, and `message`.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/feedback/loss.py` | `HumanFeedbackLoss` |
| `apps_uthereal/tests/test_feedback_loss.py` | tests |

## API surface

```python
# apps_uthereal/feedback/loss.py
"""Owner: 2-4-feedback-loss."""
from __future__ import annotations
from dataclasses import dataclass

from operad.optim.backprop.grad import TextualGradient
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer


@dataclass
class HumanFeedbackLoss:
    """`Loss`-shaped: given an answer and a HumanFeedback, return
    `(score, TextualGradient)`.

    Score semantics: `1.0 - severity` so a "this is wrong" feedback
    (severity=1.0) yields score=0; partial feedback (severity=0.3)
    yields score=0.7. The trainer uses score for callbacks (early
    stopping, best-checkpoint); the gradient drives the rewrite.
    """

    name: str = "human_feedback"

    async def compute(
        self,
        pred: ArtemisFinalAnswer,
        expected: HumanFeedback,
    ) -> tuple[float, TextualGradient]:
        """Compute the loss.

        Behavior:
          - If `expected.target_path is None`, the gradient has empty
            target_paths (the Blamer is expected to fill it in via a
            separate path; this loss is then unusable until target_path
            is set). Raise ValueError in that case — refuse to produce
            an unrouted gradient.
          - If `expected.target_path` is one of the special targets
            ("control_flow" / "data" / "no_fault"), raise
            UnactionableFeedback(reason=target_path, ...) — there is no
            leaf rewrite that fixes these.
          - Otherwise, the gradient's `message` is constructed by
            joining `final_answer_critique` and (if present)
            `desired_behavior` with `\n\nDesired behavior: `.
        """


class UnactionableFeedback(Exception):
    """Raised when feedback can't be turned into a leaf-targeted gradient."""
    def __init__(self, *, reason: str, message: str) -> None: ...
```

## Implementation notes

- **Why a `dataclass`.** Matches the pattern of `operad.metrics.LLMAAJ`
  and other `Loss`-protocol implementations in operad. Keeps the
  surface tiny.
- **Score is `1.0 - severity`.** Trivial but documented. The score is
  not what drives the optimizer — the gradient is. Score is used by
  callbacks like `BestCheckpoint` for ranking runs.
- **Refusing to produce an unrouted gradient.** The contract (C9 in
  `00-contracts.md`) says `apply_fix` mutates exactly one leaf. If
  `target_path is None` here, something upstream is broken (the Blamer
  didn't run, or its output was lost). Raising `ValueError` surfaces it
  loudly.
- **`UnactionableFeedback`.** When the Blamer says
  `target_path="control_flow"`, this loss raises so `apply_fix` can
  surface a structured error. The CLI translates it into exit code 1
  with a useful message.
- **No silent retries, no fallbacks.** If the human's feedback is too
  vague to act on, that's a real failure mode. Don't silently re-route
  to the most-recently-firing leaf.

## Acceptance criteria

- [ ] `HumanFeedbackLoss().compute(pred, fb)` returns
      `(float, TextualGradient)`.
- [ ] Returned gradient has `target_paths == [fb.target_path]` (single
      element list) when target_path is a leaf step_name.
- [ ] Returned gradient `severity == fb.severity`.
- [ ] Returned gradient `message` includes `final_answer_critique` and,
      when set, `desired_behavior`.
- [ ] Score `== 1.0 - fb.severity` clipped to `[0, 1]`.
- [ ] `compute` with `target_path is None` raises `ValueError`.
- [ ] `compute` with `target_path in SPECIAL_TARGETS` raises
      `UnactionableFeedback`.

## Tests

- `test_compute_returns_score_and_gradient` — happy path.
- `test_gradient_target_paths_single_element_list`.
- `test_gradient_severity_matches_feedback`.
- `test_gradient_message_joins_critique_and_desired_behavior`.
- `test_score_is_one_minus_severity`.
- `test_compute_raises_on_none_target_path`.
- `test_compute_raises_unactionable_on_control_flow_target`.
- `test_compute_raises_unactionable_on_data_target`.
- `test_compute_raises_unactionable_on_no_fault_target`.

## References

- `operad/optim/losses/judge.py` — `LLMAAJ` reference; same `Loss`
  shape.
- `operad/optim/backprop/grad.py` — `TextualGradient` definition.
- `operad/optim/losses/loss.py` — `Loss` Protocol.

## Notes

(Append discoveries here as you implement.)
