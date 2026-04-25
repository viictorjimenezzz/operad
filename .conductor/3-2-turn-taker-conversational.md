# Add `TurnTaker` to `operad/agents/conversational/`

## Goal
The conversational domain ships `Talker`, `ConversationTitler`, and `InteractionTitler`. `TurnTaker` is listed in the planned section and is the missing piece for structured multi-agent conversations: given a transcript and a roster of agents, decide who speaks next. Ship it as an `Agent[TurnTakerInput, TurnTakerOutput]` leaf.

## Context
- `operad/agents/conversational/` — existing leaves and shared schemas.
- `safeguard.Context` is structurally similar (classifies into a typed enum) — read it for the project's idiom around classification leaves.
- This is a leaf, not an algorithm: it returns a single typed decision. The orchestration loop that *calls* `TurnTaker` between agent turns belongs to user code (or a future algorithm).

## Scope

**In scope:**
- `operad/agents/conversational/turn_taker.py` — `TurnTaker(Agent[TurnTakerInput, TurnTakerOutput])`. Schemas: `TurnTakerInput(transcript: list[Turn], roster: list[Speaker], policy: Policy | None)`; `TurnTakerOutput(next_speaker_id: str, reason: str, confidence: float)`. Provide a `policy` knob (e.g. `"round_robin"`, `"speaker_aware"`, `"silent_ok"`) that adjusts the prompt.
- `operad/agents/conversational/schemas.py` (or `__init__.py` if schemas live there) — add the new types.
- `operad/agents/conversational/__init__.py` — re-export.
- `operad/agents/__init__.py` — re-export at the top level.
- Tests under `tests/agents/conversational/` using `FakeLeaf`-style helpers.
- Update INVENTORY §6 "Planned" → "Shipped."

**Out of scope:**
- An accompanying algorithm that drives N agents through `TurnTaker` (could be a follow-up; not this task).
- Modifying `Talker`, `ConversationTitler`, or `InteractionTitler`.
- Anything in `safeguard/`, `reasoning/`, `coding/`, `memory/`, `retrieval/`, `debate/`.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/agents/safeguard/pipeline.py`, `operad/train/callbacks.py`, `operad/optim/backward.py`, `tests/cassettes_feat/`.

## Implementation hints
- `Speaker` schema: `id: str`, `name: str`, `role_hint: str | None` (e.g. "skeptic", "moderator"). Keep it minimal.
- `Turn` schema: `speaker_id: str`, `content: str`, `tokens: int | None`.
- The leaf's `role`/`task`/`rules` should be terse and instruct the model to choose from `roster` only (rules: "Never invent a speaker_id," "Always cite the index of the last turn that influenced your choice").
- Confidence is for downstream callers' tie-breaking; use `0.0–1.0`.
- Add an `examples` list with 2-3 demonstrations of the expected JSON output to help small local models comply.

## Acceptance
- Round-trip test on the schemas.
- `FakeLeaf`-driven test demonstrating roster restriction is honored.
- Importable from `operad.agents` and `operad.agents.conversational`.
- INVENTORY updated.
