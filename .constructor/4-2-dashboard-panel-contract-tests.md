# Dashboard panels: contract tests against event schemas

## Goal
Each dashboard panel (`fitness`, `mutations`, `drift`, `training`) reads `AgentEvent` payloads with hard-coded keys. Today an algorithm refactor that renames a key silently empties the panel because the routes filter defensively (`isinstance` checks, `continue`). Add contract tests that pin: panel X requires keys [...] to render; algorithm Y emits keys [...]; the intersection is non-empty for every (panel, algorithm) pair the README claims to support.

## Context
- `apps/dashboard/operad_dashboard/routes/fitness.py` (and friends).
- `operad/algorithms/` — emitters: `EvoGradient` (mutation panel), `Sweep` (fitness curve via `generation` events), Trainer's `iteration` events (drift panel), `DataLoader` `batch_*` events (training progress).
- The contract is implicit; make it explicit and testable.

## Scope

**In scope:**
- `apps/dashboard/tests/test_panels_contract.py` (new) — per panel, define the required-key set and assert each known producer emits a superset. Use real producers running against fakes, not synthesized events, so refactors break the test.
- A small `apps/dashboard/operad_dashboard/contracts.py` (new) — a typed manifest mapping `panel_name → required_keys`. Routes can read this to fail loudly when an event lacks required keys (replace today's silent `continue` with a one-shot warning that does NOT crash the request).
- INVENTORY §13 (Dashboard panels) — table updated to cite the contract module.

**Out of scope:**
- Changing the panel UIs.
- Renaming any existing event keys (would break backward compat).
- Adding the new Sweep panel (separate task: 4-6).
- Anything outside `apps/dashboard/`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/demos/agent_evolution/`, `Makefile`, `scripts/`, `examples/benchmark/`, `operad/algorithms/sweep.py`, `apps/dashboard/operad_dashboard/routes/sweep.py` (created by 4-6), `tests/runtime/test_otel_langfuse.py` (created by 4-3).

## Implementation hints
- Per-panel test: spin up a tiny algorithm or trainer run in-process, capture events via the dashboard's existing observer, render the panel JSON, assert the panel contains rows.
- The "warn don't crash" change should emit at most one warning per (panel, missing-key) combination per process — protect with a per-key set on the panel module.
- If you discover that a panel actually *can* render with partial keys (e.g. PromptDrift without `param_changes`), document that explicitly in `contracts.py`.

## Acceptance
- Per-panel contract test passes for each documented producer.
- Routes log a warning (once) when an event misses required keys, instead of silently dropping.
- INVENTORY §13 references `contracts.py`.
