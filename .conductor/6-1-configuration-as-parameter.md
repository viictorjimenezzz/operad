# `Configuration` as a `Parameter`

## Goal
Today `temperature`, `top_p`, `model`, `backend`, `renderer` are individually trainable parameters. Lifting `Configuration` itself into a typed parameter lets `EvoGradient` (and other optimizers) mutate "the whole config" as one unit — e.g. swap from `gpt-4o-mini` to `claude-haiku-4-5` when budget tightens, or move from `chat` renderer to `xml` for schema-strict tasks. This directly serves the "prompt + sampling, not weights" thesis from VISION §1.

This task lands last because (a) it depends on the discriminated-union Configuration shape from iteration 2-1, (b) it depends on the strands decoupling from iteration 5-1 (the runner needs to handle backend-changes mid-training), and (c) it depends on hash stability (iteration 1-5) for the new parameter's deterministic identity.

## Context
- `operad/optim/parameter.py` — existing `TextParameter`, `RuleListParameter`, `ExampleListParameter`, `FloatParameter`, `CategoricalParameter`. Add `ConfigurationParameter`.
- `operad/core/config.py` — discriminated-union shape from iteration 2-1.
- `operad/core/agent.py` — the post-strands-decoupling shape from iteration 5-1.
- `operad/optim/rewrite.py` — needs a `ConfigurationRewriter` that respects the discriminated union (can't propose `model="qwen2.5"` for `backend="openai"`).
- `operad/optim/constraints.py` (or wherever constraints live) — likely a new `ConfigurationConstraint` enforcing per-backend valid choices.

## Scope

**In scope:**
- `operad/optim/parameter.py` — `ConfigurationParameter(value: Configuration, constraint: ConfigurationConstraint | None)`. Hash should be stable; rewrite must respect the discriminated union.
- `operad/optim/rewrite.py` — `ConfigurationRewriter` that proposes new `Configuration` values within the constraint's allowed shape. The LLM sees "the current config is X; the gradient is Y; suggest a better config matching this schema" with the schema embedded.
- `operad/optim/constraints.py` (or sibling) — `ConfigurationConstraint(allowed_backends: list[str], allowed_models: dict[str, list[str]], renderer_choices: list[str], temperature_range: tuple[float, float])`.
- `operad/core/agent.py` — wire `Configuration` as a parameter when `mark_trainable(config=True)` is set. `parameters()` and `named_parameters()` yield it.
- Tests under `tests/optim/` covering: parameter round-trip, rewriter proposes legal configs, constraint rejects out-of-shape ones, training a tiny agent with `EvoGradient` over `config` produces visibly different configurations.
- INVENTORY §21 — add the row.

**Out of scope:**
- Cross-backend cost normalization (a future research surface; document the gap).
- Per-task config recommendations — leave that to the LLM.
- Changing existing parameter kinds.
- Anything outside `operad/optim/`, `operad/core/agent.py`, and the related tests.

**Owned by no sibling tasks (this is a final-iteration task with no parallel siblings).**

## Implementation hints
- `ConfigurationConstraint` needs a budget knob (`max_tokens_per_run`, `max_cost_per_run`) — at least optionally — so the optimizer can prune unaffordable suggestions before invoking them. Wire to `CostTracker` if present.
- The rewriter's prompt should embed the discriminated-union JSON schema so the LLM knows the shape. Use Pydantic's `model_json_schema()` for this.
- Mid-training backend swaps interact with concurrency slots (`operad.set_limit`). Document that swapping mid-training rebuilds the slot allocation lazily — or refuses, with a clear error.
- When `freeze`/`thaw` round-trips, the config-parameter's discriminator must survive. Test this explicitly.

## Acceptance
- Parameter, rewriter, constraint all tested.
- A small EvoGradient run with a config-parameter produces visibly different configs across generations.
- Freeze/thaw round-trip works.
- INVENTORY and a short paragraph in VISION §3 document the new training surface.
