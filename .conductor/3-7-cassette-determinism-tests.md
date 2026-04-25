# Cassette-replay determinism validation matrix

## Goal
VISION §6 lists "Cassette-replay determinism validation" as the first roadmap item not yet shipped. Today there are two cassette-feat tests; neither pins the determinism guarantee end-to-end. Build the validation matrix: record once, replay N times under varied conditions, assert byte-equal traces.

## Context
- `tests/cassettes_feat/` — current shallow coverage.
- `tests/conftest.py:46+` — cassette fixture honoring `OPERAD_CASSETTE`.
- `operad/utils/cassettes.py` — recorder/replayer.
- The hash-stability fix (iteration 1) is a hard prerequisite — replays from one machine to another only become deterministic once the canonical hashing lands.
- INVENTORY §17 lists the cassette story; update it.

## Scope

**In scope:**
- `tests/cassettes_feat/test_determinism_matrix.py` (new) — the matrix:
  - Same cassette → re-run produces identical envelope (`hash_*` fields and `response`).
  - Inference replay across composite shapes: `Pipeline`, `Parallel`, `Switch`, `Router`, `ReAct`, the new `DebateAgent`/`VerifierAgent` (depend on iter 3-3 having merged).
  - Training replay: `Trainer.fit` with `OPERAD_CASSETTE=replay` produces identical `TrainingReport.epochs[*].loss` across two runs.
  - Negative case: drift detection (changed prompt, changed input) → `CassetteMiss` with the right hash segment named.
  - Cross-platform-ish smoke: spoof `time.tzname` and `locale` to two settings, assert hashes still equal (relies on iter 1 hash-stability).
- A small recorder helper that produces the cassettes used by the matrix; cassettes themselves go in `tests/cassettes_feat/cassettes/` (or wherever the existing fixtures live).
- INVENTORY §17 — replace "two tests" with the matrix description; remove from VISION §6 "Planned."

**Out of scope:**
- `Trainer.fit` cassette-aware *runtime* (separate task: 5-2). This task only validates that *recorded* training is deterministically replayable; not that the training loop can be run *against* a cassette as if it were live.
- Refactoring the recorder/replayer.
- New cassette format.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/conversational/turn_taker.py`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/agents/safeguard/pipeline.py`, `operad/train/callbacks.py`, `operad/optim/backward.py`.

## Implementation hints
- Mark the matrix `@pytest.mark.cassette_determinism` so it can be selectively run; keep it in the default offline suite so `verify.sh` exercises it.
- Use `pytest-snapshot` or write a tiny in-tree comparator — don't add a heavyweight dependency.
- Keep cassettes small; one short prompt per agent shape is enough.
- Time-zone spoof: `monkeypatch.setattr(time, "tzname", ("UTC", "UTC"))` plus `os.environ["TZ"] = "UTC"` and a `time.tzset()` call inside one test, contrasted with `"America/New_York"` in another.

## Acceptance
- Matrix test passes locally and under `OPERAD_CASSETTE=replay`.
- The drift-detection test exercises every `hash_*` segment named in INVENTORY §20.
- VISION §6 updated; INVENTORY §17 updated.
