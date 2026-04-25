# Cassette refresh: documented Makefile target + drift watchdog

## Goal
Cassettes rot quietly: there's no `make` target to refresh them, no documented workflow for "I changed a prompt, re-record." Ship a `make cassettes-refresh` target that re-records the matrix from iteration 3-7, plus a CI-friendly check that warns when cassettes are older than the agents they cover.

## Context
- `Makefile` — already exists with `make env`, `make header`, `make up`, `make demo`, `make help`.
- `tests/conftest.py` — cassette fixture on `OPERAD_CASSETTE`.
- `tests/cassettes_feat/` — cassette files; no recorder helper today beyond setting the env var.
- This task depends on iteration 3-7 (determinism matrix) being merged.

## Scope

**In scope:**
- `Makefile` — add `cassettes-refresh` target that runs the cassette matrix in record mode. Add `cassettes-check` target that runs the offline replay + reports stale cassettes (cassette mtime older than the agent's source-file mtime).
- `scripts/cassettes_check.py` (new) — small helper invoked by `cassettes-check` that reports drift candidates without failing CI (warning-only by default; `--strict` for CI fail).
- `INVENTORY.md` §17 — document the workflow.
- `README.md` — one-line addition to the Tests section pointing at `make cassettes-check`.
- The refresh target should NOT touch integration cassettes (those that hit live providers); only offline-fixture cassettes.

**Out of scope:**
- Changing the cassette format.
- Recording integration test cassettes (separate workflow, opt-in via `OPERAD_INTEGRATION`).
- Modifying the determinism matrix.
- Anything outside `Makefile`, `scripts/`, `INVENTORY.md`, `README.md`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/dashboard/`, `apps/demos/agent_evolution/`, `examples/benchmark/`, `operad/algorithms/sweep.py`, `tests/cassettes_feat/`, `tests/runtime/test_otel_langfuse.py`, `apps/dashboard/operad_dashboard/contracts.py`.

## Implementation hints
- `Makefile` syntax: keep the bash one-liners under `set -euo pipefail` for clarity.
- The drift check is heuristic — file mtime is fragile under git checkouts. Prefer a content hash: cassette file embeds the agent's `hash_content` at record time; check against current.
- Keep `cassettes-check` exit-zero by default so it can be added to CI as an informational signal; `--strict` flips to exit-non-zero for teams that want it gating.
- Document the contract in `INVENTORY.md` §17: cassettes are content-addressed, regeneration is a `make cassettes-refresh` away.

## Acceptance
- `make cassettes-refresh` re-records the offline matrix without manual intervention.
- `make cassettes-check` reports stale cassettes (test it by mutating an agent and asserting the script flags it).
- Workflow documented in `INVENTORY.md` and `README.md`.
