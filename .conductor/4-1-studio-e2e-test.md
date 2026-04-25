# Studio: end-to-end human-feedback training test

## Goal
The Studio app's whole pitch is "human rates outputs, trainer relaunches with `HumanFeedbackLoss`." Today: `HumanFeedbackLoss` is unit-tested in isolation, Studio's `TrainingLauncher` mocks `Trainer.fit`, and no test wires the full chain. Add an end-to-end test that exercises `Studio → ratings file → HumanFeedbackCallback → Trainer.fit → improved agent bundle` against an in-process fake LLM.

## Context
- `apps/studio/` — FastAPI app; `apps/studio/operad_studio/training.py` houses `TrainingLauncher`.
- `operad/train/losses_hf.py` — the loss (with the cache fix from iter 1-4).
- `operad/train/callbacks.py:HumanFeedbackCallback` — writes NDJSON rows.
- This test depends on iteration 1's `HumanFeedbackLoss` cache fix being merged.

## Scope

**In scope:**
- `apps/studio/tests/test_e2e_training.py` (new) — drive the FastAPI app via `TestClient`, simulate human rating POSTs, watch a real `Trainer.fit` run consume the ratings, assert the agent bundle's `hash_content` changed and the loss curve trends down.
- A `tests/conftest.py` fixture (or `apps/studio/tests/conftest.py`) for a deterministic fake LLM that returns scripted responses keyed by input.
- INVENTORY §21 (Human-in-the-loop) — confirm coverage in the documentation paragraph.

**Out of scope:**
- Modifying Studio's runtime behavior (only test it).
- Adding new rating UI elements.
- Changing `HumanFeedbackLoss` (separate task earlier).
- Anything in `apps/dashboard/`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/dashboard/`, `apps/demos/agent_evolution/`, `Makefile`, `scripts/`, `examples/benchmark/`, `operad/algorithms/sweep.py`, `tests/runtime/test_otel_langfuse.py` (created by 4-3).

## Implementation hints
- The test should run end-to-end in under ~5 seconds. A scripted fake LLM (lookup-table) is fastest; if you want to exercise the rewriter too, give the fake one branch that produces a "better" candidate when prompted with a critique.
- Verify the bundle round-trip: freeze before, run training, thaw after; assert different hash, same shape.
- Use `tmp_path` for the bundle and ratings dirs.
- If Studio writes ratings non-atomically, *do not* fix it here — flag a TODO and let the iter 1-4 cache code's resilience handle the half-line case.

## Acceptance
- The new e2e test passes deterministically (no flaky retries).
- It runs in `pytest tests/` and `bash scripts/verify.sh`.
- Documentation paragraph in INVENTORY §21 mentions e2e coverage.
