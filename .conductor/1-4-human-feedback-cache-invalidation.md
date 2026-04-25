# HumanFeedbackLoss: invalidate the ratings cache between epochs

## Goal
`HumanFeedbackLoss._load` (`operad/train/losses_hf.py:45-62`) caches the ratings file forever after first read. The Studio app's whole pitch is that a human rates outputs *while* training runs — but the trainer never sees new ratings. Make the loss reload when the file changes (mtime-based) and expose an explicit `reload()` for callers who want to force it.

## Context
- The Studio app (`apps/studio/`) appends rating rows to an NDJSON file via `HumanFeedbackCallback`. Training runs in the background and its `HumanFeedbackLoss._by_id` cache is populated on the first call and never refreshed.
- This is the single biggest reason the human-in-the-loop story doesn't actually close the loop today.

## Scope

**In scope:**
- `operad/train/losses_hf.py` — replace the unconditional cache hit with an mtime check, add `reload()` method, default to "reload if file mtime changed since last read."
- `tests/train/test_human_feedback.py` (or wherever the loss is tested) — add a test that writes a row, computes loss, appends another row, recomputes loss, asserts the new row is visible.

**Out of scope:**
- Studio app behavior — its FastAPI side doesn't change.
- `HumanFeedbackCallback` — touched only if it owns the cache (it doesn't).
- Any change to `Trainer.fit` cadence.

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/train/callbacks.py`, `operad/train/trainer.py`, `operad/optim/*`, `operad/utils/*`, `operad/runtime/*`, `operad/data/*`, `operad/core/agent.py`, `examples/`.

## Implementation hints
- mtime-based invalidation is enough; this isn't a high-frequency hot path.
- Be defensive about partial writes: if a JSONL parse fails, log via `operad.observers` logger and keep the previous cache rather than crashing the trainer. Studio writes are not yet atomic (separate concern); your code shouldn't blow up training when it sees a half-line.
- Consider adding `reload_per_epoch: bool = True` for callers who want stricter semantics.

## Acceptance
- New test demonstrates that rows appended mid-training become visible on the next loss call.
- Existing tests unchanged.
- Partial-line resilience exercised by a test.
