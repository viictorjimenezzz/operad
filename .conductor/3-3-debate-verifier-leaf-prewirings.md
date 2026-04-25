# Pre-wired `Debate` and `Verifier` leaves under `agents/reasoning/`

## Goal
The `Debate` and `VerifierLoop` algorithms exist (`operad/algorithms/`). Users today cannot drop either into a `Pipeline` as a leaf because the algorithm shape (`run(...)`) is not the agent shape (`__call__(x: In) -> Out`). Add `agents/reasoning/debate.py` and `agents/reasoning/verifier.py` — `Agent[In, Out]` wrappers that own the orchestration internally and expose a single typed contract, parallel to how `react.py` wraps a multi-step reasoning loop.

## Context
- `operad/agents/reasoning/react.py` — the canonical example of a pre-wired composite leaf. Read it first.
- `operad/algorithms/debate.py` and `operad/algorithms/verifier_loop.py` — the underlying orchestrators. Reuse them; do not duplicate logic.
- The point is *user ergonomics*: `Pipeline(planner, Debate(...), summarizer)` should just work.

## Scope

**In scope:**
- `operad/agents/reasoning/debate.py` — `DebateAgent(Agent[Q, A])` that wraps `algorithms.Debate` with sensible defaults (proposer, critic, synthesizer, rounds). Accepts the underlying components as kwargs so users can swap them. Forward the algorithm's events through the agent's observer surface.
- `operad/agents/reasoning/verifier.py` — `VerifierAgent(Agent[Q, A])` wrapping `algorithms.VerifierLoop`. Accept `generator`, `verifier`, `max_iter`, `threshold`.
- `operad/agents/reasoning/__init__.py` — re-export both.
- `operad/agents/__init__.py` — re-export at top level.
- Tests under `tests/agents/reasoning/` that pin: typed I/O, drop-into-Pipeline composition, event forwarding.
- INVENTORY §6 — drop from "Planned," add rows.

**Out of scope:**
- Modifying the underlying algorithms — only wrap them.
- Adding new debate/verifier variants (single-turn vs multi-turn, etc.).
- Anything in `conversational/`, `safeguard/`, `coding/`, `memory/`, `retrieval/`, `debate/`.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/conversational/turn_taker.py`, `operad/agents/safeguard/pipeline.py`, `operad/train/callbacks.py`, `operad/optim/backward.py`, `tests/cassettes_feat/`.

## Implementation hints
- These are *composite* agents (no `forward` calculation), but not `Pipeline`/`Parallel`. Override `forward(x)` to call the wrapped algorithm and return its result. The composite-router rule says "don't inspect payload values" — these wrappers don't; they delegate to the algorithm.
- The `build()` walk should still introspect the inner agents (proposer/critic/synthesizer for debate; generator/verifier for verifier). Make sure the wrapped algorithm exposes them so `build()` can type-check the inner edges.
- Forward observer events with the wrapper's `agent_path` prefix so the dashboard groups them under the wrapper node.
- Hash content: include the underlying components' hashes so two `DebateAgent`s with different critics hash differently.

## Acceptance
- `Pipeline(leaf_a, DebateAgent(...), leaf_b)` builds and runs in a test.
- Events from inside Debate appear in the trace under the wrapper's path.
- INVENTORY updated.
