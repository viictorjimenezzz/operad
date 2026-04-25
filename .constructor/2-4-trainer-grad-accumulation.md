# Trainer: clean up cross-batch gradient accumulation

## Goal
`Trainer._train_batch` (`operad/train/trainer.py:410-441`) merges per-sample grads with a `pending = [p.grad]` term that captures whatever was left from the *previous* batch when `accumulation_steps > 1`. The intention is accumulation, but the merge concatenates an already-merged gradient (containing N joined messages) with M fresh per-sample grads — producing either redundant message duplication or unbounded prompt size. Audit `_merge_grads`, define the accumulation contract, and fix the merge to satisfy it.

## Context
- `operad/train/trainer.py:410-441` — the per-batch grad collection loop.
- `_merge_grads` lives in `operad/train/_merge.py` (or wherever the helper sits — verify) and currently joins `message` strings with `\n---\n`, unions `target_paths`, takes max severity.
- The semantics of "accumulation" should be: across `accumulation_steps` batches, the optimizer sees a single grad whose message preserves *each sample once*, not "batch-1's merged blob + batch-2's individual samples."

## Scope

**In scope:**
- `operad/train/trainer.py` — change cross-batch accumulation so the merge always sees per-sample atoms (e.g. accumulate per-sample lists across batches, merge once at step time). Document the accumulation contract in `Trainer.fit`'s docstring.
- `operad/train/_merge.py` (or wherever `_merge_grads` lives) — if it can't tell "atomic" from "already-merged" grads, give it that ability (e.g. preserve a `parts: list[TextualGradient] | None`) or restructure so the accumulator never has to ask.
- A regression test under `tests/train/` that runs three batches with `accumulation_steps=3`, asserts the gradient seen by `optimizer.step()` mentions exactly N samples (not N + previous merge).

**Out of scope:**
- Changing the per-sample backward call.
- Changing the `Optimizer.step` API.
- Per-parameter-kind merge variations (single shape is enough).

**Owned by sibling iter-2 tasks — do not modify:**
- `operad/core/*`, `operad/runtime/observers/otel.py`, `operad/agents/reasoning/components/tool_user.py`, `operad/optim/*`, `operad/train/callbacks.py`, `operad/train/losses_hf.py`.

## Implementation hints
- Cleanest: store `accumulator: dict[id(p), list[TextualGradient]]` on the Trainer, append per-sample grads from every batch, merge once when `step()` fires.
- Severity policy under accumulation: `max` is what's documented; don't change without explicit decision.
- Token-budget the merged message: if the joined messages would exceed a sane cap (e.g. 32k chars), summarize older entries via the same `GradSummarizer` `MomentumTextGrad` uses — but only if the cap is hit; don't pre-summarize.

## Acceptance
- New accumulation test passes: gradient at `step()` references each per-sample message exactly once across the accumulated batches.
- Existing trainer tests pass.
- Docstring on `Trainer.fit` clearly states the accumulation contract.
