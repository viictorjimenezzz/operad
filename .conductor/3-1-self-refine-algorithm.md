# Add the `SelfRefine` algorithm

## Goal
The README and VISION list `SelfRefine` as planned. It's the second-most-cited agentic loop after ReAct (Madaan et al., 2023): generator produces a draft → reflector emits critique → refiner edits draft → loop until convergence or `max_iter`. Ship it as a first-class algorithm in `operad/algorithms/`.

## Context
- `operad/algorithms/` — existing peers: `Beam`, `Debate`, `VerifierLoop`, `Sweep`, `AutoResearcher`, `TalkerReasoner`. They are plain classes with `run(...)` (not `Agent` subclasses) — keep that invariant.
- `VerifierLoop` is the closest cousin (generator + verifier loop). Read it first to match the project's idiom.
- Reference paper: "Self-Refine: Iterative Refinement with Self-Feedback" (Madaan et al., 2023). The on-policy variant where generator and refiner share parameters is the natural fit; the cross-policy variant (separate refiner agent) should be available too.

## Scope

**In scope:**
- `operad/algorithms/self_refine.py` — `SelfRefine(generator, reflector, refiner=None, max_iter=N, stop_when=callable)`. If `refiner is None`, reuse `generator` (on-policy). Loop: produce → reflect → refine → score (optional) → repeat. Emit `AlgorithmEvent`s per iteration so the dashboard's drift/iteration panels pick it up.
- `operad/algorithms/__init__.py` — re-export.
- Tests under `tests/algorithms/` covering: convergence on a fake "always good" reflector, max-iter cutoff, on-policy and cross-policy modes, event emission.
- Update `INVENTORY.md` §7 to add the row, drop it from "Planned."

**Out of scope:**
- The `agents/reasoning/self_refine.py` leaf prewiring (a separate task could add it; not part of this iteration's plan).
- Adding new metric kinds.
- Modifying any existing algorithm.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/agents/conversational/*`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/agents/safeguard/pipeline.py`, `operad/train/callbacks.py`, `operad/optim/backward.py`, `tests/cassettes_feat/`.

## Implementation hints
- Take typed `In`/`Out`/`Critique` generics so the algorithm composes with other operad shapes.
- Termination should be expressible by `stop_when(state)` callback OR a `min_score` against an optional `metric=`. Don't bake one policy.
- Emit `iteration` events with `{iter: i, draft_hash: ..., critique_summary: ...}` payload — the dashboard's drift panel already consumes that schema.
- Concurrency: the refine step is sequential by nature; don't try to parallelize iterations. `Beam`-style breadth on a single iteration's draft is a future addition; don't pre-empt.
- Read `operad/algorithms/verifier_loop.py` for the project's preferred control-flow style and event-emission patterns; mirror them.

## Acceptance
- All new tests pass.
- `from operad.algorithms import SelfRefine` works.
- INVENTORY.md updated.
- Convergence test demonstrates real refinement (score improves monotonically with a deterministic fake reflector).
