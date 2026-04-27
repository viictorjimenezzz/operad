# METAPROMPT - Agent onboarding for operad

This file routes agents to the right context before editing. Keep it short;
the detailed explanations belong in the linked docs and nearby code.

## Purpose

Use this as a map, not a rulebook. Read the files that match your task,
then follow `AGENTS.md` for repo-wide working rules.

## Start here

1. `AGENTS.md` - agent behavior, codebase invariants, and verification rules.
2. `README.md` - current status, public surface, install, and test commands.
3. `VISION.md` - architecture, component boundaries, and the library's direction.
4. `ISSUES.md` - known risks, gaps, and footguns.
5. Any active task brief in `.conductor/` (e.g. `.conductor/dashboard-redesign/`) — scope and acceptance criteria.

## Subsystem map

- Core, config, and build flow: `operad/core/README.md`, `operad/core/config.py`
- Agents and reusable components: `operad/agents/README.md`
- Algorithms: `operad/algorithms/README.md`
- Metrics and benchmarking: `operad/metrics/README.md`, `operad/benchmark/README.md`
- Optimization and training: `operad/optim/README.md`, `operad/train/README.md`, `TRAINING.md`
- Runtime and observability: `operad/runtime/README.md`
- Test patterns and offline harnesses: `tests/conftest.py`

## Before editing

- Inspect the nearest implementation and tests before changing code.
- State assumptions when the task has multiple plausible interpretations.
- Keep the change scoped to the user's request and the active brief.
- Preserve the architecture in `VISION.md` and the invariants in `AGENTS.md`.
- Prefer linking to authoritative docs over copying long explanations here.
- DO NOT KEEP BACKWARDS COMPATIBILITY, CHANGE EVERYTHING THAT IS NEEDED FOR THE NEW CODE TO WORK!!

## Before PR

- Run the narrow relevant tests first.
- Run `uv run pytest tests/` when practical.
- Run `uv run python -c "import operad"` after changes to exports, package layout, or public APIs.
- Update nearby docs when behavior, imports, or public APIs change.
