# Harden `build()`: leaf-config presence + sentinel containment

## Goal
Two related build-time gaps in `operad/core/build.py`:

1. **None-config slips through.** A leaf without a `config` passes `build()` validation today; the failure only surfaces when `forward()` reaches `self.config.io.structuredio` and crashes with `AttributeError`. README claims errors fire "before a single token is generated" — make that true for the missing-config case.

2. **Sentinel can leak across composite boundaries.** When a child composite's `forward()` returns a `model_construct()` sentinel, the parent composite receives it without tripping the trace-time guard. A composite that bypasses its children entirely (returning a constant) silently corrupts the graph. Tag the sentinel and refuse to accept it back at composite boundaries unless it came from a real child invocation.

## Context
- `operad/core/build.py` — `Tracer`, sentinel proxy, validation walk.
- The "composites are routers, not calculators" invariant is load-bearing per VISION §2.1; this fix protects it from a clever-but-broken implementation upstream.

## Scope

**In scope:**
- `operad/core/build.py` — add a `requires_config_at_build: bool` (default True) on the leaf validation path; reject `None` config there with a `BuildError` carrying a Mermaid fragment per the existing pattern. Tag sentinels with a "tainted unless touched by a real child" marker; fail composite output validation if the marker survives.
- Tests under `tests/core/` covering: leaf with `config=None`, composite that returns a hard-coded constant, composite that returns the proxy unchanged, composite that legitimately returns a child's output.

**Out of scope:**
- `operad/core/agent.py` (separate task: 2-3 owns it).
- `operad/core/config.py` (separate task: 2-1 owns it).
- `operad/core/models.py`.
- Anything in `operad/runtime/`, `operad/optim/`, `operad/train/`.

**Owned by sibling iter-2 tasks — do not modify:**
- `operad/core/agent.py`, `operad/core/config.py`, `operad/core/models.py`, `operad/train/trainer.py`, `operad/runtime/observers/otel.py`, `operad/agents/reasoning/components/tool_user.py`.

## Implementation hints
- Sentinel taint: a `_OperadSentinelMeta` flag (`tainted: bool = True`) cleared only by the real child invocation path inside `Tracer.record`. On exit from a composite's traced forward, if the returned object's metadata still says `tainted`, raise.
- For the None-config check, traverse leaves only. Composites are allowed to omit `config`.
- Error messages should follow the existing `BuildError(input_mismatch, ...)` style with a Mermaid fragment so the user sees the offending node visually.

## Acceptance
- All four new tests pass.
- Existing build/trace tests pass.
- `BuildError` messages include the offending agent path and a Mermaid fragment.
