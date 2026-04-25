# Pre-wired safety pipeline composite

## Goal
`safeguard.Context` and `safeguard.Talker` ship as separate leaves. Today users wire `Pipeline(Context, Talker)` themselves and have to hand-roll the "if classified as in-scope, pass through; otherwise emit refusal" routing. That makes safeguarding feel like a sketch, not a feature. Ship a pre-wired `SafetyGuard` composite that does the routing.

## Context
- `operad/agents/safeguard/` — existing `Context`, `Talker`, and shared schemas (`SafeguardCategory`).
- `operad/agents/reasoning/switch.py` — the existing `Switch` primitive. The composite can be implemented on top of it.
- This is *not* the same as a guardrail framework; we're shipping the missing default pipeline, not replacing GuardrailsAI/NeMo.

## Scope

**In scope:**
- `operad/agents/safeguard/pipeline.py` — `SafetyGuard(Agent[In, Out])` that internally builds `Context → Switch{IN_SCOPE → passthrough_or_user_provided_inner, OUT_OF_SCOPE → Talker_refusal}`. Accept an optional `inner: Agent[In, Out]` (the protected agent) and an optional `refusal_template: str`.
- `operad/agents/safeguard/__init__.py` — re-export `SafetyGuard`.
- `operad/agents/__init__.py` — re-export at top level.
- Tests under `tests/agents/safeguard/` using `FakeLeaf`-style classifiers covering: in-scope passthrough, out-of-scope refusal, custom inner agent, observer events for both branches.
- Update INVENTORY §6 (`safeguard/`) to list `SafetyGuard`.

**Out of scope:**
- Adding new categories to `SafeguardCategory`.
- Replacing the existing `Context` or `Talker` leaves.
- Anything in `reasoning/`, `conversational/`, `coding/`, `memory/`, `retrieval/`, `debate/`.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/conversational/turn_taker.py`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/train/callbacks.py`, `operad/optim/backward.py`, `tests/cassettes_feat/`.

## Implementation hints
- Build on `Switch` rather than re-implementing routing. `Switch` already carries the build-time validation for typed branches.
- `inner` defaults to a passthrough leaf — when nothing is supplied, `SafetyGuard` is a fancy way to emit "yes, this is in scope" and forward the request unchanged. That's still useful for benchmarks.
- The refusal path must produce the same `Out` type as the inner agent. If `Out` doesn't have an obvious "refused" representation, surface that as a build-time error pointing the user at `refusal_factory: Callable[[In, SafeguardCategory], Out]`.
- Do not emit a "blocked" `AgentEvent` in a way that conflicts with the Switch's existing event schema; align with the dashboard's expectations.

## Acceptance
- Both branch tests pass.
- Build-time error fires when `Out` cannot be constructed for refusal and no `refusal_factory` is given.
- Importable from `operad.agents` and `operad.agents.safeguard`.
- INVENTORY updated.
