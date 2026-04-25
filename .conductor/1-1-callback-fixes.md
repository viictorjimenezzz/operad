# Fix EarlyStopping patience off-by-one (and audit related comparisons)

## Goal
`EarlyStopping` in `operad/train/callbacks.py:142` uses `if self._stale > self.patience:` — with `patience=3` it stops after **4** non-improving epochs, not 3. Match the Lightning/Keras convention (`>=`) and audit the rest of the callback module for the same family of threshold-comparison errors.

## Context
- `operad/train/callbacks.py:142` — confirmed off-by-one.
- Same file ships `BestCheckpoint`, `PromptDrift`, `LearningRateLogger`, `MemoryRotation`, `HumanFeedbackCallback`, `GradClip` — at least the first three have monitor/threshold comparisons that deserve a once-over while you're in there.

## Scope

**In scope:**
- `operad/train/callbacks.py` — fix `EarlyStopping`, audit similar comparisons elsewhere in the file, document min-delta semantics in docstrings if currently ambiguous.
- `tests/train/test_callbacks.py` (or whichever file currently covers callbacks) — pin the corrected stop-epoch and any other comparisons you tightened.

**Out of scope:**
- Adding the `Curriculum` callback (separate task, iteration 3).
- Touching `Trainer.fit` callback dispatch.
- Anything outside `operad/train/callbacks.py` and its test file.

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/runtime/observers/base.py`, `operad/optim/*`, `operad/train/losses_hf.py`, `operad/utils/hashing.py`, `operad/data/samplers.py`, `operad/core/agent.py`, `examples/`.

## Implementation hints
- Convention: stop after the `patience`-th non-improving epoch — i.e. `_stale >= patience`. Reset `_stale` on improvement, keep `min_delta` semantics intact.
- Add a regression test: feed a fake metric stream with the trainer mocked, assert the exact epoch index where `_should_stop` flips.
- If you find a similar bug in `BestCheckpoint` (e.g. tie-breaking on equal scores) or `PromptDrift` (e.g. drift threshold using `>` where `>=` is more useful), fix it and document the choice in the docstring.

## Acceptance
- New regression test pins the off-by-one fix.
- All existing callback tests still pass.
- No behavior change outside `train/callbacks.py` and its test file.
