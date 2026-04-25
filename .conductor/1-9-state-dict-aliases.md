# Add `state_dict`/`load_state_dict` aliases on `Agent`

## Goal
INVENTORY.md §21 admits this is open work: PyTorch muscle-memory expects `state_dict()` / `load_state_dict()`, but `Agent` exposes only `state()` / `load_state()`. The rest of the spine (`Optimizer`, `LRScheduler`) already uses `state_dict` / `load_state_dict`, creating a jarring inconsistency. Add the canonical aliases without breaking the existing ones.

## Context
- `operad/core/agent.py` — `state()` (snapshot of declared attributes) and `load_state(snapshot)` already exist.
- The aliases must not cause tests that grep for one or the other to drift; both names must exist and behave identically.
- This is a tiny change but it's surface API; treat it as such.

## Scope

**In scope:**
- `operad/core/agent.py` — add `state_dict()` returning the same payload as `state()`; add `load_state_dict(snapshot)` delegating to `load_state(snapshot)`.
- A short docstring on each alias pointing to its canonical sibling and noting the equivalence.
- Tests under `tests/core/` that pin: both pairs are interchangeable, the snapshot round-trips, and naming a kwarg as one or the other works.
- A one-line entry in `INVENTORY.md` §1 confirming the aliases ship.

**Out of scope:**
- Refactoring `state()` / `load_state()` — they remain canonical.
- Changing the snapshot payload shape.
- Aliases on `Optimizer` or `LRScheduler` (already consistent).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/optim/*`, `operad/train/*`, `operad/runtime/*`, `operad/utils/*`, `operad/data/*`, `examples/`.

## Implementation hints
- One-liner `state_dict = state` is fine if and only if both names show up in `dir(agent)` — verify with a test.
- If you prefer explicit forwarding methods (clearer in tracebacks), do that.
- Don't introduce deprecation warnings; both names are equally first-class.

## Acceptance
- Round-trip test passes for both pairs.
- `dir(Agent)` test confirms both names exposed.
- INVENTORY entry added.
