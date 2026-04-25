# 2-1 — Run-list IA & sidebar

> **Iteration**: 2 of 4 (frontend infrastructure). **Parallel slot**: 1.
> **Owns**: the runs-list page, its sidebar, run-row component, and
> filter/search store.
> **Forbidden**: the renderer (2-2 owns), pinned-runs store (2-3 owns),
> any backend code, any layout JSON, any chart component.

## Problem

After iter-1 lands, `/runs` will return only non-synthetic algorithm
runs by default. But the current runs-list UI:

- Is a flat sidebar with no grouping by algorithm class.
- Uses chip-filters (all/algorithms/agents) that no longer match the
  data model (synthetic runs are hidden by default at the API level).
- Has no search, no time-range, no pagination, no virtualization.
- Doesn't support multi-select for cross-run comparison (iter-4-1's
  killer feature needs it).
- Doesn't surface algorithm-relevant signals on each row (latest
  best-score, generations elapsed, status dot).

Users land on the dashboard and see a wall of hex IDs.

## Scope

### Owned files

- `apps/frontend/src/dashboard/pages/RunListPage.tsx`
- `apps/frontend/src/shared/panels/run-list-sidebar.tsx` (currently
  unused dead code per the explore agent's findings; you may revive
  or replace it).
- `apps/frontend/src/stores/ui.ts` (filter & search state goes here
  if you keep using this slice).
- `apps/frontend/src/hooks/use-runs.ts` (extend the query to use new
  query params from 1-2: `?include=synthetic`, `?groupBy=algorithm`,
  search text, time-range — whatever the backend exposes).
- New: `apps/frontend/src/shared/panels/run-row.tsx` — a single-row
  component with status dot, algorithm badge, key metrics, multi-select
  checkbox, pin star.
- New: `apps/frontend/src/shared/panels/run-group-section.tsx` — a
  collapsible section per algorithm class.
- New: `apps/frontend/src/shared/ui/search-input.tsx` (only if no
  shadcn input is already there to reuse).
- Tests under `apps/frontend/src/**/*.test.tsx`.

### Forbidden files

- `apps/frontend/src/components/DashboardRenderer.tsx` (2-2).
- `apps/frontend/src/hooks/use-event-stream.ts`,
  `use-panel-stream.ts` (2-2).
- `apps/frontend/src/registry/` (2-2).
- `apps/frontend/src/stores/pinned-runs.ts` (2-3 creates this; you
  consume it via the hook).
- Any layout JSON, any chart component, any backend code.

## Direction

### Information architecture

Group runs by algorithm class first. Suggested hierarchy:

```
ALGORITHMS
├─ EvoGradient
│  ├─ run id #1 (status, best, generations, started)
│  ├─ run id #2
│  └─ ...
├─ Trainer
│  └─ ...
└─ Debate
   └─ ...

(toggle) show inner runs
```

The "show inner runs" toggle calls `?include=synthetic` and renders an
"Inner runs" section grouped under their parent.

### Per-row content

Each row shows (in order):
1. Status dot (running/ended/error).
2. Algorithm class badge (or "AGENT" for non-algorithm runs).
3. The key metric for the algorithm:
   - EvoGradient: `best=1.000  gen=5/6`
   - Trainer: `loss=0.0823  epoch=3/10`
   - Debate: `consensus=0.83  rounds=4`
   - Beam: `top=0.94  candidates=12`
   - default: `events=N`
4. Started time (relative: "2m ago").
5. Multi-select checkbox.
6. Pin star (calls `usePinnedRuns().toggle(runId)` from 2-3).

Resolve the per-algorithm metric via a small registry — e.g. a map
from `algorithm_class` → `(run: RunSummary) => string`. Be liberal:
if metric data isn't in the summary, fall back to "events=N".

### Search & filters

- Search input filters by run-id prefix, algorithm class, or
  algorithm path (case-insensitive).
- Time-range: chip group "all / 1h / 24h / 7d".
- Status: chip group "all / running / ended / errors".
- Show synthetic toggle (default off).

State lives in `stores/ui.ts` (or a new `stores/runs-filter.ts` slice
if you prefer). Persist filter state to `sessionStorage` so a
refresh doesn't drop the user's view.

### Multi-select & comparison

- Shift-click to select a range; cmd/ctrl-click to toggle individual.
- Sticky footer shows "N selected" with a "Compare" button.
- "Compare" button navigates to `/experiments?runs=a,b,c` (route is
  introduced in 4-1; before that, just point at a placeholder route or
  a dialog that says "comparison coming soon").

### Virtualization

If the registry has 100+ runs, the sidebar must virtualize. Use
`react-window` or `@tanstack/react-virtual`. Don't introduce a new
heavyweight scroll library if `@tanstack/react-virtual` is already in
the lockfile (check first).

### Empty state

When there are no runs:
- Show a clear "no runs yet" card.
- Include a copy-paste-able command:
  `uv run python apps/demos/agent_evolution/run.py --offline --dashboard`
- Link to the "writing an agent" docs.

## Acceptance criteria

1. After running the agent_evolution demo, the runs list shows **one**
   EvoGradient row with `best=1.000  gen=5/6` (or similar).
2. Toggling "show inner runs" reveals the synthetic children grouped
   under their parent.
3. Filter chips, search, and time-range all work and persist across
   refresh.
4. Multi-select + Compare navigates to `/experiments?runs=…`.
5. Pin star toggles a run's pinned state via the 2-3 hook.
6. Page renders smoothly with 200+ runs (no jank).
7. Tests under `apps/frontend/src/dashboard/pages/RunListPage.test.tsx`
   covering: filter logic, multi-select, group rendering.

## Dependencies & contracts

### Depends on

- 1-2: `/runs?include=synthetic`, `/runs/{id}/children`, the
  `synthetic` and `parent_run_id` fields on summaries.
- 2-3: `usePinnedRuns()` hook, `<PinIndicator />` component.

### Exposes

- A multi-select selection state that 4-1 will consume via URL
  parameter (`/experiments?runs=…`).
- A reusable `<RunRow />` component that other pages may want.

## Direction notes / SOTA hints

- shadcn/ui has a Command palette pattern that's nice for search +
  filter + jump. Optional but worth considering.
- For algorithm-class grouping with collapse, a simple
  `<details>` / `<summary>` is fine; resist building a heavyweight
  Tree component.
- For status dots, a single CSS animation + `aria-label="running"`
  beats a third-party loader library.

## Risks / non-goals

- Don't fetch every run's panel data (fitness, drift) on the list
  page — that's the renderer's job.
- Don't add a "delete run" button (registry is in-memory and there's
  no API for it; 4-4 may add it).
- Don't cross-import from `studio/`.

## Verification checklist

- [ ] Demo run shows up correctly grouped.
- [ ] Filter chips + search persist across refresh.
- [ ] Multi-select Compare navigates correctly.
- [ ] `make frontend-test` and `make frontend-typecheck` pass.
- [ ] Playwright sanity: open dashboard, see runs, click into one,
      navigate back — no console errors.
