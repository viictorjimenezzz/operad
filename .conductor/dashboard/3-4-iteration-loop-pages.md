# 3-4 — Iteration-loop layouts (Beam, VerifierLoop, SelfRefine)

> **Iteration**: 3 of 4. **Parallel slot**: 4.
> **Owns**: three layouts (one upgrade + two new), one shared
> "iteration progression" component, optional new backend routes.
> **Forbidden**: other layouts/components.

## Problem

Three operad algorithms share a structural pattern: an iteration loop
that produces candidates per step and converges (or doesn't):

- **Beam**: generates N candidates per step, scores, keeps top-K.
- **VerifierLoop**: generate → verify → exit when score ≥ threshold or
  max_iter hit.
- **SelfRefine**: generate → reflect → refine, exit on approval.

All three are interesting to visualize but currently:

- **Beam**: layout exists but is minimal — only shows candidate
  scatter + top-K table.
- **VerifierLoop**: no layout. Falls through to default.
- **SelfRefine**: no layout. Falls through to default.

A common pattern they share: per-iteration `score`, `phase`, optionally
`text` (the candidate / proposed answer). The dashboard should provide
a unified "iteration progression" component, then specialize per
algorithm.

## Scope

### Owned files

- `apps/frontend/src/layouts/beam.json` (extend)
- New: `apps/frontend/src/layouts/verifier.json`
- New: `apps/frontend/src/layouts/selfrefine.json`
- `apps/frontend/src/shared/charts/beam-candidate-chart.tsx` (extend)
- New: `apps/frontend/src/shared/charts/iteration-progression.tsx` —
  per-iteration step card with score + text + phase badge. Reused by
  all three algorithms.
- New: `apps/frontend/src/shared/charts/convergence-curve.tsx` — the
  score(iteration) plot with threshold reference line.
- New: `apps/dashboard/operad_dashboard/routes/iterations.py` — generic
  endpoint serving iteration events for any of these three algorithms
  (since they all use `kind="iteration"` events).
- Tests.

### Forbidden files

- Other layouts, other algorithm components.

## Direction

### Investigate the runtime

Read:

- `operad/algorithms/beam.py`
- `operad/algorithms/verifier_loop.py`
- `operad/algorithms/self_refine.py`

Confirm what events each emits. Per the explore agent's report, they
all emit `iteration` events with varying payloads (`phase`,
`iter_index`, `score`, etc.). Verify exact field names.

### Generic backend route

Add `GET /runs/{id}/iterations.json` that returns:

```
{
  "iterations": [
    {"iter_index": int, "phase": str, "score": float | null,
     "text": str | null, "metadata": {...}}
  ],
  "max_iter": int | null,
  "threshold": float | null,
  "converged": bool | null
}
```

Plus the SSE variant. Field names should match what the runtime
already emits — don't transform.

### `<IterationProgression />` component

A generic vertical timeline of iteration steps:

- Each step: phase badge (color-coded per phase), iter_index, score,
  collapsed-by-default text body.
- Highlight the converged-on iteration.
- Diff view between consecutive iterations' text (use the
  `prompt-drift-diff` component from 3-1 if helpful, or roll your
  own — but coordinate to avoid duplication).

### `<ConvergenceCurve />`

A line chart of score over iterations:

- X axis: iter_index.
- Y axis: score.
- Horizontal reference line at the threshold (if any).
- Vertical reference line at the converged iteration.
- For Beam, this becomes "best score per step"; for VerifierLoop,
  "verifier score per attempt"; for SelfRefine, "approval probability
  per refine cycle".

### Beam upgrade

Today's `beam-candidate-chart.tsx` shows a scatter of `(candidate_index,
score)`. Extend with:

- **Top-K diff viewer**: select 2-3 candidates from the top-K, show
  their text side-by-side.
- **Pruning visualization**: highlight which candidates were dropped
  at each step (if the runtime emits step-by-step pruning events).
- **Score distribution histogram**: aggregated across all candidates.

### VerifierLoop layout

```
verifier.json tabs:
  - Overview: convergence curve + iteration progression
  - Verifier feedback: per-iteration verifier critique text
  - Graph
  - Events
```

### SelfRefine layout

```
selfrefine.json tabs:
  - Overview: convergence curve + iteration progression with phase
    badges (refine/reflect alternating)
  - Refinements: text-diff per refine cycle
  - Reflections: list of reflection critiques
  - Graph
  - Events
```

## Acceptance criteria

1. Run a Beam demo → see candidate scatter + top-K diff + pruning.
2. Run a VerifierLoop demo → see convergence curve hitting threshold.
3. Run a SelfRefine demo → see refine/reflect alternation in
   progression timeline.
4. The `<IterationProgression />` component renders consistently
   across all three layouts.
5. Tests pass for the new route, components, and three layouts.

## Dependencies & contracts

### Depends on

- 1-1, 1-2, 2-2, 2-3, 3-5.
- Optionally consumes the `<PromptDriftDiff />` component from 3-1
  (if coordinating during implementation; otherwise build inline).

### Exposes

- `<IterationProgression />` and `<ConvergenceCurve />` as reusable
  primitives.
- `/runs/{id}/iterations.json|.sse`.

## Direction notes / SOTA hints

- Phase color mapping: a small CSS variable per phase. Pick a
  consistent palette (e.g. `phase-generate=blue`, `phase-verify=green`,
  `phase-reflect=amber`, `phase-refine=violet`).
- Convergence detection: client-side, walk iterations and find first
  one where `score >= threshold`.
- For VerifierLoop's "would have stopped at iter X" simulator, just
  let the user click on a point in the convergence curve to mark it.

## Risks / non-goals

- Don't try to unify Beam and the others fully — Beam's candidate
  fan-out per step is structurally different (it generates N
  candidates per iteration; the others generate 1).
- Don't add a "re-run from iteration N" feature.
- Don't hand-craft cassettes for tests; use fixtures or generate
  on-the-fly.

## Verification checklist

- [ ] All three demos render correctly.
- [ ] Top-K diff in Beam works for 2 and 3 candidates.
- [ ] Convergence threshold reference line draws correctly.
- [ ] Tests pass.
