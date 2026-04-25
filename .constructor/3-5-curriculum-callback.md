# `Curriculum` callback: re-order training data by gradient severity

## Goal
Textual-gradient training is far more sample-efficient if the rewriter sees its worst critiques during the high-LR window. Add a `Curriculum` callback that, after each epoch, re-orders the next epoch's data by descending `Loss.severity` — hardest examples late in the high-LR phase, then mixed once LR decays. This is the prompt-level analog of curriculum learning (Bengio et al., 2009) and pairs naturally with `WarmupLR` + `CosineExplorationLR`.

## Context
- `operad/train/callbacks.py` — existing callbacks: `EarlyStopping`, `BestCheckpoint`, `GradClip`, `PromptDrift`, `LearningRateLogger`, `MemoryRotation`, `HumanFeedbackCallback`.
- `operad/data/` — `DataLoader`, samplers. The callback re-permutes indices via the dataloader's sampler.
- This task lands after iteration 1's callback fixes are merged, so you can rely on the corrected `EarlyStopping` and any audit findings.

## Scope

**In scope:**
- `operad/train/callbacks.py` — add `Curriculum(monitor: str = "severity_per_sample", mode: str = "hard_first" | "easy_first" | "anneal", warmup_epochs: int = 1)`. The callback installs a permuter on the loader's sampler at `on_epoch_end`.
- `operad/data/samplers.py` — if the existing samplers don't expose a "set custom permutation for next epoch" hook, add one minimally.
- Tests under `tests/train/` covering: severity-based ordering, anneal mode, warmup respected, no-op when severities are uniform.
- INVENTORY §21 — add the callback row.

**Out of scope:**
- Cross-epoch metric tracking machinery (use what's already in `Trainer.epoch_history`).
- New samplers other than the hook.
- Modifying `Trainer.fit` invocation order.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/conversational/turn_taker.py`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/agents/safeguard/pipeline.py`, `operad/optim/backward.py`, `tests/cassettes_feat/`.

## Implementation hints
- "Severity per sample" needs to be tracked somewhere. The simplest path: have the trainer expose `trainer.last_epoch_per_sample_severity: dict[int, float]` (sample-index → severity) populated during `_train_batch` (the iteration-2 task touches this code; coordinate via the merged file).
- "anneal" mode = hard-first for the first `warmup_epochs`, then random thereafter — matches what curriculum-learning literature suggests and avoids overfitting to the order.
- Document the interaction with `WeightedRandomSampler` and `StratifiedSampler` (iteration 1) — typically the curriculum overrides them; warn if both are configured.

## Acceptance
- Re-ordering test pins the index sequence.
- Anneal-mode test pins the post-warmup randomness.
- Documentation updated.
