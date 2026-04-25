# Eliminate side effects from `Agent.__init__`

## Goal
VISION §8 explicitly forbids side effects in `__init__` — "no network, no provider handshakes, no model loading." `Agent.__init__` (`operad/core/agent.py:267-277`) currently mutates the `Configuration` via `model_copy()` when `default_sampling` is set. It's a copy so the original isn't observably mutated, but it still violates the rule and creates asymmetry: a user who constructs an Agent never gets back the same `Configuration` instance they passed in. Move the merge into `build()` (or first invocation) where it belongs.

## Context
- `operad/core/agent.py` — `__init__`, `default_sampling` handling, the strands-state shadowing dance at `_init_strands` (also a candidate for cleanup but separate concern; leave the shadowing alone unless removing it costs nothing).
- The fix is structural: defer the merge until the moment a config is actually used.

## Scope

**In scope:**
- `operad/core/agent.py` — drop the `model_copy()` mutation in `__init__`. Compute the effective sampling at the call site (`forward`, `format_*_message`, wherever sampling is read) by composing class-level `default_sampling` with the live `config.sampling`. Provide a `_effective_config` (or `_resolve_sampling`) helper rather than scattering merge logic.
- Tests under `tests/core/` that pin: identity-preservation (`agent.config is original_config`), sampling override priority (instance kwargs > `default_sampling` > backend defaults), and that `freeze`/`thaw` still produces an equivalent agent.

**Out of scope:**
- Removing the strands state-shadowing hack (separate concern; iteration 5 strands decoupling).
- Changing `Configuration` semantics (separate task: 2-1).
- Build-time validation tweaks (separate task: 2-2).
- Anything in `operad/optim/`, `operad/train/`, `operad/runtime/` that reads sampling — those callers should still get the merged value via the new helper.

**Owned by sibling iter-2 tasks — do not modify:**
- `operad/core/build.py`, `operad/core/config.py`, `operad/core/models.py`, `operad/train/trainer.py`, `operad/runtime/observers/otel.py`, `operad/agents/reasoning/components/tool_user.py`.

## Implementation hints
- Effective-sampling resolution should be cheap; don't recompute on every event.
- If a downstream caller (e.g. `format_user_message`) currently reads `self.config.sampling.temperature` directly, route it through `self._effective_sampling()`.
- `state()` snapshot already excludes runtime artifacts; double-check the new helper doesn't accidentally land in the snapshot.

## Acceptance
- Identity-preservation test passes (config object is not replaced).
- Sampling-merge tests pin the priority order.
- `freeze`/`thaw` round-trip equivalent.
- `INVENTORY.md` §1 docstring updated if the agent table mentions `default_sampling`.
