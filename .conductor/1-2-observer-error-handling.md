# Make observer errors loud (without breaking the pipeline)

## Goal
`ObserverRegistry.notify` in `operad/runtime/observers/base.py:60-66` swallows every observer exception with a bare `except Exception: pass`. A broken observer (dashboard down, OTel exporter mis-configured, cassette path unwritable) disappears silently. Keep the "observer failures must not break the pipeline" invariant, but surface the failure: log once per observer, increment a counter, and offer a strict mode that re-raises for tests.

## Context
- `operad/runtime/observers/base.py:60-66` — current swallow.
- The registry is called on every event in every invocation; logging on every failure is noisy. We want loud-but-bounded.
- Observers in tree: `JsonlObserver`, `RichDashboardObserver`, `OtelObserver`, `TraceObserver`, `TrainerProgressObserver`, plus any user-registered ones.

## Scope

**In scope:**
- `operad/runtime/observers/base.py` — add bounded logging (per-observer first-failure log via `logging`), per-observer error counter exposed via `registry.errors()` or similar, and an `OPERAD_OBSERVER_STRICT` env var (or registry kwarg) that re-raises.
- A small unit test that registers an exploding observer and asserts: the agent run completes, the failure is logged, the counter increments, and strict-mode re-raises.

**Out of scope:**
- Refactoring individual observers; their `on_event` methods are not yours.
- Changing the `Observer` protocol shape — keep it backward-compatible.
- Wiring the strict env var into CI (do that in iteration 4 if useful).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/train/*`, `operad/optim/*`, `operad/utils/*`, `operad/data/*`, `operad/core/agent.py`, `examples/`.

## Implementation hints
- Use `logging.getLogger("operad.observers")`; emit at WARNING for first occurrence per observer, DEBUG afterwards (use a per-observer "already-warned" flag).
- Counter shape: `dict[id(observer), int]` is fine; expose via a method on `ObserverRegistry`.
- For strict mode, prefer a constructor kwarg on `ObserverRegistry` that reads `OPERAD_OBSERVER_STRICT` once at init — avoid `os.environ` reads on the hot path.
- Don't swallow `asyncio.CancelledError` — re-raise it. That's a common pitfall with bare-except in async code.

## Acceptance
- Exploding-observer test passes; strict-mode re-raise test passes.
- Existing observer tests unchanged.
- No new dependencies.
