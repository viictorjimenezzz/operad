# 07-01 Convergence — polish, audit, QA

**Branch**: `dashboard/convergence`
**Wave**: Sequence 7 (single task)
**Dependencies**: every earlier brief
**Estimated scope**: medium

## Goal

After Sequences 1-6 merge, this brief is a single agent doing the
final pass: register conflicts (mostly the per-algo `registry.tsx`
imports), do a color/density audit, run all tests, do manual QA
against examples 01-04 plus a fresh sweep, and update docs.

## Why this exists

The wave engine guarantees disjoint files within a sequence but the
component registry (`apps/frontend/src/components/algorithms/registry.tsx`)
and the dashboard renderer (`apps/frontend/src/components/runtime/dashboard-renderer.tsx`)
are append-only; merge conflicts are trivial but real. Plus the
ambient quality bar (W&B-level polish) is worth a final dedicated
pass.

## Files to touch

- `apps/frontend/src/components/algorithms/registry.tsx` — verify
  every per-algo brief registered cleanly.
- `apps/frontend/src/components/runtime/dashboard-renderer.tsx` —
  verify every reserved element type from `00-contracts.md` §11 is
  registered.
- `apps/frontend/src/styles/tokens.css` — final pass: any
  ad-hoc colors slipped through? Any density inconsistencies?
- `apps/dashboard/README.md` — update to reflect new tab structure
  per algorithm rail.
- `apps/dashboard/tests/test_smoke.py` (create or extend) — high-level
  smoke test for every algorithm class.
- This file — fill in lessons learned.

## Implementation steps

### Step 1 — Registry verification

For each entry in `00-contracts.md` §11, assert:
- A component file exists at the expected path.
- It's exported from the per-algo folder's index.
- It's registered in `registry.tsx` and/or
  `dashboard-renderer.tsx`.

If any reserved type is missing, file follow-up issues; do not
implement here.

### Step 2 — Color audit

Grep for ad-hoc hex / hsl / rgb in `apps/frontend/src/`; expected
zero matches outside `tokens.css` and possibly the chart libs'
internal usage. Fix any leakage.

```bash
rg --type=ts --type=tsx '#[0-9a-fA-F]{3,8}\b|hsl\(|rgb\(' apps/frontend/src/ \
  | rg -v 'tokens\.css|hash-color\.ts'
```

Should produce no results.

### Step 3 — Density audit

Grep for nested `rounded-lg border` to catch the bordered-card-
within-card antipattern:

```bash
rg --type=tsx 'rounded-lg.*border.*bg-bg' apps/frontend/src/
```

Manually inspect each match; if it's a nested card, refactor to a
divider.

### Step 4 — Manual QA against examples 01-04

Run each example with `--dashboard`, navigate every rail (agents,
algorithms, training, opro), every algorithm tab, every drawer
state, every keyboard shortcut. Document any visual or functional
regressions in this file under "Lessons learned" before merging.

### Step 5 — Test sweep

```bash
cd apps/frontend && pnpm test --run
uv run pytest apps/dashboard/tests/ -v
uv run pytest tests/ -q             # if anything in operad/ touched
make build-frontend                  # SPA bundle compiles
uv run python -c "import operad"     # public API still importable
```

All green.

### Step 6 — Docs update

- `apps/dashboard/README.md` — refresh the "What you see" section
  with the new per-rail tab structure.
- `INVENTORY.md` §13 — add the dashboard panels table updated to
  reflect StructureTree + ParameterDrawer + per-class tabs.

## Acceptance criteria

- [ ] Registry has every reserved type from `00-contracts.md` §11.
- [ ] No ad-hoc hex / hsl / rgb colors outside the palette.
- [ ] No nested bordered-card antipattern.
- [ ] All tests pass; `make build-frontend` succeeds.
- [ ] Manual QA on examples 01-04 produced no regressions, OR
  regressions are documented and patched here.
- [ ] Docs reflect the new structure.

## Lessons learned

(Fill in during the convergence pass; this section becomes the seed
for future planning.)

- Surprise: …
- Underestimated: …
- Overestimated: …
- For next redesign: …

## Out of scope

- New features. This is convergence-only.

## Stretch goals

- Add a `__dev/primitives` gallery entry for every new primitive
  introduced by Sequence 1-6 so future agents have a visual
  reference.
- Add a `make redesign-smoke-test` that boots the dashboard,
  attaches each example, and screenshots each rail.
- A short "Dashboard cookbook" doc with screenshots of each
  per-algorithm rail's typical appearance.
