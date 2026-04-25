# RewriteAgent: schema-aware retry hints on Pydantic validation failure

## Goal
When the rewriter produces output that fails Pydantic validation (most often `ExampleListRewriter` returning malformed JSON for the `input`/`output` fields of an `Example`), the retry prompt today says only "violated the constraint." Pipe the actual `ValidationError.errors()` payload into the tightened retry prompt so the LLM knows exactly which field, expected what type, and got what bad value.

## Context
- `operad/optim/rewrite.py` — `apply_rewrite` and the per-kind rewriters (`TextRewriter`, `RuleListRewriter`, `ExampleListRewriter`, `FloatRewriter`, `CategoricalRewriter`).
- `ExampleListRewriter` is the worst offender because nested Pydantic models give the LLM a lot of room to fail.
- Reference: this is the single highest-leverage change to lift `apply_rewrite` reliability per the review.

## Scope

**In scope:**
- `operad/optim/rewrite.py` — extend the retry-prompt construction to include a structured "previous attempt failed because" block whenever the failure was a `pydantic.ValidationError`. Keep coercion-failure (constraint mismatch) retries as they are unless schema info would help.
- A test under `tests/optim/` that uses a fake LLM emitting deliberately-bad JSON, asserts the second-attempt prompt contains the field path and expected type from the validation error.

**Out of scope:**
- The OPRO / APE / Momentum optimizer correctness fixes (separate task: 1-3).
- Adding new constraint kinds.
- Refactoring how rewriters are dispatched.

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/optim/momentum.py`, `operad/optim/opro.py`, `operad/optim/ape.py`, `operad/optim/sgd.py`, `operad/optim/parameter.py`, `operad/optim/backward.py`, `operad/train/*`, `operad/runtime/*`, `operad/utils/*`, `operad/core/agent.py`, `examples/`.

## Implementation hints
- `ValidationError.errors()` returns a list of dicts with `loc`, `msg`, `type`. Render only the first 5 errors to keep token count bounded.
- Trim verbose `input` value reprs to ~200 chars per error.
- Place the hint above the retry instruction so the LLM reads it before being asked to try again.
- Update each rewriter's docstring with one sentence describing what kind of schema feedback it surfaces.

## Acceptance
- New retry-prompt-content test passes.
- Existing rewrite tests pass unchanged.
- Manual eyeball check: a fake `Example` schema mismatch produces a readable, bounded error block in the prompt.
