# 4-1 — Cross-run experiments comparator

> **Iteration**: 4 of 4 (composite). **Parallel slot**: 1.
> **Owns**: a NEW `/experiments` route, an experiments page, and
> overlay/diff components.
> **Forbidden**: existing per-algorithm layouts/components.

## Problem

The single feature that would make the dashboard genuinely useful for
research-style work — **comparing N runs side-by-side** — does not
exist. Every analytical question that spans runs (did optimizer A
beat B? did this rule survive across seeds? what changed between two
training configs?) is impossible today.

This is the dashboard's load-bearing differentiator vs Langfuse:
Langfuse traces *one* run; the dashboard compares *experiments*.

## Scope

### Owned files

- New: `apps/frontend/src/dashboard/pages/ExperimentsPage.tsx`
- New: `apps/frontend/src/dashboard/routes.tsx` — register the new
  route. **Note**: 4-2 and 4-3 also add routes; coordinate via small
  textual merges. Each adds a single `<Route path="..."
  element={<...Page />} />` line. Conflicts auto-resolve.
- New: `apps/frontend/src/shared/charts/curve-overlay.tsx` —
  multi-series fitness/loss curve.
- New: `apps/frontend/src/shared/charts/multi-prompt-diff.tsx` — N-way
  text diff.
- New: `apps/frontend/src/shared/charts/cost-vs-quality-scatter.tsx` —
  scatter with Pareto frontier overlay.
- New: `apps/frontend/src/shared/charts/operator-radar.tsx` — radar
  chart of mutation operator wins per run.
- Tests.

### Forbidden files

- Existing layouts (`evogradient.json`, etc.).
- Existing chart components owned by iter-3.
- Backend code beyond a small `/runs/_compare` helper if needed.

## Direction

### Route + URL

```
/experiments?runs=run_id_1,run_id_2,run_id_3
```

The page reads run-ids from the URL search params (single source of
truth). It also reads from the `usePinnedRunSummaries()` hook (2-3) so
that even without URL params, all currently-pinned runs are
comparable. URL takes precedence when both are present.

### Page IA

```
┌──────────────────────────────────────────────────────┐
│ EXPERIMENTS — comparing 3 runs                       │
│ [Add run ↓]    [Clear all]                           │
├──────────────────────────────────────────────────────┤
│  metadata table: run_id, algorithm, started, dur...  │
├──────────────────────────────────────────────────────┤
│  ┌──── curve overlay (fitness or loss) ────────┐    │
│  │   3 series, legend with method/seed/run_id  │    │
│  └─────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────┤
│  ┌── cost vs quality scatter ──┐  ┌── operator radar│
│  │  one dot per run, Pareto    │  │  per-run radar  │
│  │  frontier overlay           │  │  of op success  │
│  └─────────────────────────────┘  └─────────────────┘
├──────────────────────────────────────────────────────┤
│  ┌──── final-prompt diff (3-way) ───────────────┐    │
│  │  text diff with "kept in 2 of 3" highlights  │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### Adapter — what to compare

Different algorithms have different "score" curves. Build a small
adapter:

- EvoGradient: `fitness.json[].best`.
- Trainer: `loss curve` (train).
- Debate: per-round agreement.
- Beam/Verifier/SelfRefine: convergence curve.

If runs are heterogeneous (one EvoGradient + one Trainer), normalize
by step index and label the y-axis "primary metric (varies)". Don't
silently misalign.

### Multi-prompt diff

For 2 runs: standard side-by-side diff.
For 3+ runs: show each run's prompt as a column; highlight tokens
that survived in ≥2 columns. This is the "consensus prompt"
visualization.

You can use `diff-match-patch` or implement a simple "longest common
sub-sequence per token" approach. Don't over-engineer; markdown-style
diffs are fine.

### Cost vs quality scatter

X axis: total tokens or USD spent.
Y axis: final best score / loss.
One dot per run; label with method/seed.
Pareto frontier overlay (the convex hull of "best for this cost").

### Operator radar

For runs that emit mutation events (EvoGradient and similar):
show a radar with one axis per operator (`append_rule`,
`set_temperature`, ...) and a polygon per run showing the operator
success rate.

### Persistence

Pinned runs from 2-3 are localStorage-persisted. The URL is the
ephemeral comparison context. The page should:

- On mount: read `?runs=` if present; else use pinned runs; else
  show empty state with a CTA to pin runs from the runs list.
- "Add run" button: opens a small picker (existing runs list, in
  modal form) and appends to the URL.
- "Clear all": clears URL params (does not unpin from the store).

## Acceptance criteria

1. From the runs list, multi-select 2 EvoGradient runs and click
   Compare. The `/experiments?runs=…` page renders curves overlaid,
   prompts diffed, costs scattered.
2. Pin 3 runs across the dashboard, navigate to `/experiments`
   directly. The page loads with all 3.
3. Compare heterogeneous runs (1 EvoGradient + 1 Trainer): the curve
   overlay normalizes by step index without crashing.
4. Multi-prompt diff highlights consensus correctly for N=3.
5. Pareto frontier draws correctly when one run strictly dominates
   another.
6. Tests cover: URL parsing, adapter selection, diff highlighting,
   Pareto computation.

## Dependencies & contracts

### Depends on

- 2-1: multi-select Compare button navigates here.
- 2-3: `usePinnedRunSummaries()` hook.
- 3-x: each algorithm has a stable `.json` endpoint for its primary
  curve.

### Exposes

- `<CurveOverlay />`, `<MultiPromptDiff />`,
  `<CostVsQualityScatter />`, `<OperatorRadar />` as reusable
  primitives.

## Direction notes / SOTA hints

- For Pareto frontier: sort by X, walk and keep points whose Y
  is strictly better than the running best. ~10 lines.
- For diff-match-patch: a small library; useful for token-level
  diffing.
- Recharts has `<RadarChart />` built in.

## Risks / non-goals

- Don't add statistical significance tests (e.g. confidence intervals
  on score differences) — punt to a future task.
- Don't try to compare more than 5 runs visually well; for >5,
  collapse to a tabular summary with sparklines.
- Don't allow editing/saving experiment definitions — this is an
  ephemeral comparison view, not a saved-experiment tracker.

## Verification checklist

- [ ] All four primitive components have tests.
- [ ] Demo: pin 3 EvoGradient runs, view `/experiments`, see
      everything render.
- [ ] Heterogeneous comparison degrades gracefully.
- [ ] URL is the source of truth for the comparison set.
