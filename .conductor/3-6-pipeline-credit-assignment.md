# `BackpropAgent` with real credit assignment for `Pipeline`

## Goal
`backward.py:103-124` (the Pipeline rule) hands the full output gradient to the last stage and a `model_copy()` to every earlier stage. That's not credit assignment — it's "blame everyone equally." Build a `CreditAssignAgent` (an `Agent[CreditInput, dict[path, GradOut]]`) that splits the gradient across stages based on which earlier outputs the reflector identifies as load-bearing for the failure. This is the natural "agents improving agents" extension of the spine.

## Context
- `operad/optim/backward.py` — the per-composite-kind backprop rules.
- `operad/optim/rewrite.py` — pattern for `Agent`-shaped optim helpers (`RewriteAgent`).
- VISION §2.3 — algorithms making agents better; the credit-assignment LLM is itself an `Agent`.

## Scope

**In scope:**
- `operad/optim/credit_assign.py` (new) — `CreditAssignAgent(Agent[CreditAssignInput, CreditAssignOutput])` that takes `(stages: list[StageRecord], terminal_grad: TextualGradient)` and emits `{stage_path: TextualGradient}`. The terminal gradient becomes the input; the LLM blames specific stages.
- `operad/optim/backward.py` — Pipeline rule consults `CreditAssignAgent` if one is configured on the trainer/optimizer; falls back to current "broadcast copy" behavior if not. Configurable via `Trainer(credit_assign=...)` or registered globally.
- Tests under `tests/optim/` using a `FakeLeaf` credit-assigner that returns hard-coded mappings; assert each stage's `Parameter.grad` ends up with the right severity/message.
- Schema: `StageRecord(path, input, output, prompt_summary)`; `CreditAssignOutput(per_stage: dict[str, TextualGradient])`.

**Out of scope:**
- Credit assignment for `Parallel` (same shape, separate concern; can follow). Document that gap explicitly.
- Credit assignment for `Switch` (the routed branch is the obvious recipient; no reflector needed).
- Changing `BackpropAgent` registration mechanism beyond what's needed.

**Owned by sibling iter-3 tasks — do not modify:**
- `operad/algorithms/self_refine.py`, `operad/agents/conversational/turn_taker.py`, `operad/agents/reasoning/debate.py`, `operad/agents/reasoning/verifier.py`, `operad/agents/safeguard/pipeline.py`, `operad/train/callbacks.py`, `tests/cassettes_feat/`.

## Implementation hints
- The credit-assigner's prompt should receive *summaries* of each stage's I/O, not full transcripts — token budget matters. Trim per-stage to ~500 chars of input/output excerpt.
- Severity policy: the per-stage severities returned by the LLM should be normalized so the per-stage sum doesn't exceed the terminal severity — bake that into the loss for the credit-assigner or into a post-processing step.
- Make the credit-assigner *optional*. Default off so existing behavior is preserved; the Trainer's `credit_assign=ConfiguredCreditAssign(...)` opts in.
- Read TextGrad's blame-routing logic for inspiration if it's accessible; don't replicate naively — operad's path identifiers are stable, theirs aren't.

## Acceptance
- Fake-LLM credit-assignment test passes.
- Default-off behavior unchanged from current Pipeline rule.
- Docstring on `CreditAssignAgent` describes the contract precisely; INVENTORY updated.
