# 5-5 — Cassette replay validation for training runs

**Wave.** 5 (depends on 4-3, 5-1).
**Parallel with.** 5-1, 5-2, 5-3, 5-4.

## Context

Operad's offline test strategy rests on cassette replay
(`operad.utils.cassette`). Inference calls are recorded once with a
real backend and replayed deterministically on every subsequent run.
For training runs to be trustable in CI, the same property must hold:
given the same seeds, a training run must produce the same final
agent state byte-for-byte against the recorded cassette.

This task writes the integration test that proves that property, and
fixes any missing seed paths discovered along the way.

Read `operad/utils/cassette.py`, `operad/utils/hashing.py`, and
`.context/NEXT_ITERATION.md` §16.5.

## Scope — in

### `tests/optim/test_cassette_training.py`

- Setup:
  - Reuse 5-1's `FakeLeaf` + fake rewriter / backprop agents *or* —
    preferably — use *real* leaves pointed at a local llama-server
    for the cassette recording, then replay offline.
  - If using real: gate the record phase on
    `OPERAD_INTEGRATION=llamacpp`; the replay phase runs without
    that env var.
- Recording phase (manual, not run in CI):
  - `OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp uv run pytest
    tests/optim/test_cassette_training.py -v`
  - Produces `tests/optim/_cassettes/cassette_train.jsonl`.
- Replay phase (CI default):
  - `uv run pytest tests/optim/test_cassette_training.py -v`
  - Loads the cassette; runs the full training loop; asserts the
    *final* `hash_content`, the per-epoch `TrainingReport`, and the
    final per-parameter values all match the recorded run.
  - If they drift, `CassetteMiss` names which hash segment diverged.
- Assertions:
  - Final agent's `hash_content` is byte-identical to the expected
    value (commit the expected hash as a constant in the test).
  - `len(TrainingReport.epochs) == epochs` (no short-circuit /
    accidental skipping).
  - Each epoch's `hash_content` matches the expected sequence.
  - Optimizer's `state_dict` at end of run matches expected.

### Potential fixes as discovered

While implementing this, audit the training pipeline for hidden
nondeterminism. Possible leaks:

- `DataLoader` with `shuffle=True` but no seed default — fix the
  default to `None` + document the determinism implication.
- `asyncio.gather` ordering: if the test observes non-deterministic
  order in backward propagation, you'll need to canonicalize
  downstream. Likely fix: sort entries by `started_at` then by
  path, deterministically.
- `momentum_state` ordering if serialized in arbitrary dict order —
  use `sorted(dict.items())` when hashing.

Add a small doc `operad/optim/DETERMINISM.md` listing every seed
surface a user must lock to get deterministic replay.

## Scope — out

- Do **not** change the `operad/utils/cassette.py` behavior beyond
  clearly-scoped bug fixes with a PR description naming the symptom.
- Do not add nondeterminism remediation to production code unless
  you find a specific bug; fixes go into scoped PRs, not this test.
- Do not require CI to run the recording phase. Recording is a
  manual / integration-only step.

## Dependencies

- 4-3: `Trainer`.
- 5-1: `examples/train_demo.py` helpers (importable via
  `examples._train_helpers`).
- Existing: `operad.utils.cassette`, `operad.utils.hashing`.

## Design notes

- **Expected values.** Commit them *after* a clean record+replay
  cycle. Do not hand-compute them; take whatever the test observes
  on day one of a clean machine, record both the cassette and the
  expected values in the same PR.
- **Two-phase test.** The test should detect whether it's recording
  or replaying based on `OPERAD_CASSETTE`. In record mode it
  *captures* actual values; in replay mode it *asserts* them.
  (The existing cassette machinery should support this pattern;
  verify with its docs.)
- **Diffing failures.** When a replay fails, print a structured
  report: which epoch first diverged, the hash delta, which
  parameter's value changed. Reuse `trace_diff` infrastructure if
  it fits; otherwise a small ad-hoc diff is fine.
- **Slow path.** This test can take a few seconds — that's fine. It
  does not have to be in the fast-path suite; add it to the default
  `pytest tests/` run but leave a way to skip it
  (`pytest -k "not cassette_training"`).

## Success criteria

- `uv run pytest tests/optim/test_cassette_training.py` passes on a
  clean checkout with the committed cassette.
- Intentionally perturbing a seed makes the test fail with a useful
  `CassetteMiss`-style error.
- `operad/optim/DETERMINISM.md` (new file, ~200 words) lists every
  seedable surface in the training stack.
- No regressions in the existing cassette tests.
