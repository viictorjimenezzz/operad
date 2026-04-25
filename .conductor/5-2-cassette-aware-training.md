# Cassette-aware training: replay `Trainer.fit` from a recorded run

## Goal
The cassette layer makes inference replayable. Make training replayable too: record a `Trainer.fit` run once, replay it byte-equal in CI as a regression test for any prompt-level change. This is "regression-test a prompt edit" — an enterprise-grade story the typed-orchestration crowd will care about.

## Context
- `operad/utils/cassettes.py` — recorder/replayer; today only inference traffic is captured.
- `operad/train/trainer.py` — the loop that needs to be cassette-aware.
- Iteration 1's hash-stability fix is required.
- Iteration 3-7's determinism matrix is required (the record/replay primitives are exercised there for inference; this task extends them to training).

## Scope

**In scope:**
- `operad/utils/cassettes.py` — extend the cassette schema (or add a sibling cassette type) to record: per-sample loss values, per-sample gradients (the `TextualGradient` payloads), optimizer step inputs (rewriter inputs/outputs), LR schedule state. Replay these instead of computing them.
- `operad/train/trainer.py` — when running under `OPERAD_CASSETTE=replay`, skip the live LLM calls inside `_train_batch` and instead pull pre-recorded gradients and rewriter outputs from the cassette. Live mode unchanged.
- `tests/cassettes_feat/test_training_replay.py` (new) — record a 2-epoch run on a tiny dataset; replay; assert byte-equal `TrainingReport.epochs[*]` (every loss, every parameter post-step value).
- INVENTORY §17 — extend the cassette description to mention training replay.
- VISION §6 — close the loop on the "Cassette-replay determinism validation" item.

**Out of scope:**
- Recording arbitrary Python state (e.g. random seeds) — the trainer already takes a `seed`. If determinism still slips, that's a separate hash-stability bug.
- Training from a cassette in *speedup* mode (skip the rewriter). That's a research direction, not an MVP.
- Modifying the optimizer fleet.
- Anything in `operad/core/`, `operad/agents/`, `apps/`, `examples/`.

**Owned by sibling iter-5 tasks — do not modify:**
- `operad/core/agent.py`, `operad/core/build.py`, `operad/core/models.py`, `operad/core/_strands_runner.py` (5-1 owns).

## Implementation hints
- The cassette key for a training step is a function of `(epoch, batch_idx, sample_idx, agent_hash_content, input_hash, parameter_paths)`. Bake all of these into the lookup key so a small change forces a clean miss with a clear `CassetteMiss` message.
- Don't try to replay the *output* of the agent under training — that's already covered by inference cassettes. Replay the *gradient* — that's the unit of training-time work.
- Consider a separate file extension (`.train.jsonl` vs `.jsonl`) so users don't get confused about what's recorded.
- `Trainer.fit` should detect a training cassette presence and switch automatically; users shouldn't need a separate flag.
- The `LR` scheduler's `state_dict` should round-trip through the cassette so a replay's LR trajectory is identical.

## Acceptance
- Training cassette test passes: record once, replay produces byte-equal report.
- A negative test (modify the agent's `rules` between record and replay) raises `CassetteMiss` with the offending hash segment.
- INVENTORY and VISION updated.
