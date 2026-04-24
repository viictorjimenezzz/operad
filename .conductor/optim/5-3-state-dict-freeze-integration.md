# 5-3 — `state_dict` aliases + freeze/thaw integration

**Wave.** 5 (depends on 2-1, 4-3).
**Parallel with.** 5-1, 5-2, 5-4, 5-5.

## Context

Users with PyTorch muscle memory reach for `model.state_dict()` and
`model.load_state_dict(sd)`. Today operad exposes `state()` /
`load_state()` and `freeze()` / `thaw()` for the same idea. This
task adds the familiar aliases and confirms `freeze()` round-trips
a trained agent cleanly — including any optimizer state if the user
passes it.

Read `operad/core/agent.py` (state / load_state), `operad/core/freeze.py`,
and `.context/NEXT_ITERATION.md` §"state_dict()".

## Scope — in

### `operad/core/agent.py`

- Add two thin aliases on `Agent`:
  - `state_dict(self) -> AgentState` — returns `self.state()`.
  - `load_state_dict(self, sd: AgentState) -> None` — delegates to
    `self.load_state(sd)`.
  - Preserve both old names for backward compatibility. Add short
    docstrings on both new aliases pointing at the old names.

### `operad/core/freeze.py`

- Extend `freeze()` / `thaw()` to optionally include optimizer state:
  - `freeze(agent, path, *, optimizer: Optimizer | None = None)` —
    if provided, `optimizer.state_dict()` is dumped into the frozen
    artefact under a new `optimizer_state` key.
  - `thaw(path) -> (Agent, optimizer_state: dict | None)` — tuple
    return when the artefact contains optimizer state; otherwise
    returns just the Agent (backward compatible).
  - Add a second entry point `thaw_pair(path) -> tuple[Agent, dict
    | None]` so callers who always want the tuple don't have to
    runtime-check. The single `thaw()` remains as-is to avoid
    breaking callers.
- Preserve the existing "API keys stripped automatically" invariant
  for optimizer state too — scrub any nested `Configuration` inside
  rewriter-cached configs.

### `operad/train/callbacks.py` (small edit)

- `BestCheckpoint` now optionally passes the trainer's `optimizer`
  to `freeze()` so that a resumed training run restores optimizer
  state exactly.

### Tests

- `tests/core/test_state_dict_aliases.py`:
  - `agent.state_dict()` returns the same object as `agent.state()`.
  - `agent.load_state_dict(sd)` mirrors `agent.load_state(sd)`.
- `tests/core/test_freeze_with_optimizer.py`:
  - `freeze(agent, "/tmp/f.json", optimizer=opt)` + `thaw_pair` round-
    trip: the reloaded agent has the expected `hash_content`; the
    reloaded optimizer's `state_dict()` matches the original.
- `tests/train/test_best_checkpoint_resume.py`:
  - After `BestCheckpoint` writes, we can `thaw_pair` and resume
    training from the checkpoint; training continues and further
    improves the val metric.

## Scope — out

- Do **not** rename or remove `state()` / `load_state()`. Aliases
  only.
- Do not change the existing `freeze()` signature in a backward-
  incompatible way. `optimizer=None` is the default.
- Do not add a filesystem scanner / versioned checkpoint tree — just
  the single-file round trip.

## Dependencies

- 2-1: `parameters()` / `mark_trainable` (so the round-trip has
  something to freeze).
- 3-2: `Optimizer.state_dict` / `load_state_dict`.
- 4-3: `BestCheckpoint`, `Trainer`.
- Existing: `operad.core.freeze`, `operad.core.state`.

## Design notes

- **Serialization format.** The frozen artefact is JSON today.
  Optimizer state adds nested dicts (per-param momentum state,
  RNG state as needed). Pydantic-dump everything; no pickle.
- **Rewriter config scrubbing.** Optimizer state may carry
  `RewriteAgent` instances with live `Configuration`s. Before
  dumping, strip `api_key` / auth headers just like the existing
  `freeze()` does.
- **Cassette interaction.** A frozen-then-thawed training run
  should still replay cleanly under `OPERAD_CASSETTE=replay` as
  long as the seeds match. Add one integration test that
  demonstrates this.
- **PyTorch parity.** Document in the docstring that
  `state_dict()` aliases `state()`: this is to make typing it from
  muscle memory work. The canonical name in operad is still
  `state()`.

## Success criteria

- New tests pass offline.
- Existing `freeze()` / `thaw()` tests still pass unchanged.
- `uv run ruff check operad/core/{agent,freeze}.py operad/train/callbacks.py`
  clean.
- Resuming a training run from a checkpoint works (continues
  improving on the val metric).
- No edits to `operad/optim/*` beyond test-only additions.
