# `Configuration.backend` as the actual single source of truth

## Goal
The VISION promises that `Configuration.backend` is authoritative — no hidden fallbacks. Today the validator allows `backend="openai"` paired with a local `host`, and the failure surfaces as a runtime `AssertionError` deep inside `resolve_model()` (`operad/core/models.py`). Lift that to a build-time `BuildError` (or Pydantic `ValidationError`) the moment the `Configuration` is constructed.

## Context
- `operad/core/config.py` — current validator only catches a narrow case.
- `operad/core/models.py` — adapter dispatch contains `assert cfg.host is not None` (and similar) for local backends, plus implicit choices about which env vars are read for hosted ones.
- The fix is shape: each backend has known requirements (`host` for local, `api_key` for hosted, `region` for `bedrock`, etc.). Encode those requirements once.

## Scope

**In scope:**
- `operad/core/config.py` — replace permissive validation with a per-backend constraint table or discriminated union, raising at construction time when a `Configuration` is internally inconsistent (local backend without host, hosted without API key when no env fallback is configured, batch=True on a backend that doesn't support batch).
- `operad/core/models.py` — replace the runtime `assert`s with explicit error types if anything slips through, and remove silent env-var fallbacks that contradict the "single source of truth" promise. Keep documented fallbacks (e.g. `OPENAI_API_KEY`) but make them visible by emitting a debug log when used.
- Tests under `tests/core/` that exhaustively pin each backend's required-field set and the failure modes.

**Out of scope:**
- Adding new backends.
- Changing the `Sampling` / `Resilience` / `IOConfig` sub-models' fields.
- Touching `Agent.__init__` config-mutation behavior (separate task: 2-3).
- Touching `core/build.py` (separate task: 2-2).

**Owned by sibling iter-2 tasks — do not modify:**
- `operad/core/build.py`, `operad/core/agent.py`, `operad/train/trainer.py`, `operad/runtime/observers/otel.py`, `operad/agents/reasoning/components/tool_user.py`.

## Implementation hints
- Pydantic's discriminated union (`Annotated[Union[...], Field(discriminator="backend")]`) is the cleanest expression. Each variant is a small subclass of the common `Configuration` shell.
- Document explicitly in the `Configuration` docstring which env vars each backend reads and when. List the precedence order.
- Don't break `freeze`/`thaw` — the redaction at freeze time still needs to work; ensure variant types round-trip.
- For backends that support `batch`, gate the flag in the variant schema; for those that don't, raise on construction.

## Acceptance
- Per-backend validation tests pass; old assertion sites in `models.py` are unreachable in tests.
- `freeze`/`thaw` round-trip test passes for at least two backend variants.
- `INVENTORY.md` §10 updated to reflect the discriminated-union shape.
