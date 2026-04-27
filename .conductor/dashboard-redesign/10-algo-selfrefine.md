# 10 — Algorithm: SelfRefine

**Stage:** 3 (parallel; depends on Briefs 01, 02, 15)
**Branch:** `dashboard-redesign/10-algo-selfrefine`
**Subagent group:** C (Algos-narrative)

## Goal

SelfRefine is a `(generate → reflect → refine)` loop. The view should
read like a *ladder of revisions*: each iteration is a triplet of
generate, reflect, refine, with the reflection's critique driving the
next refinement. Surface the convergence threshold, show the score
trajectory, and make the textual evolution from iteration to iteration
the centerpiece.

## Read first

- `operad/algorithms/srefine.py` — `SelfRefine.run()` lines 96-197.
  Events:
  - `algo_start` (lines 100-105): `{max_iter}`
  - `iteration phase="refine"` (lines 132-140): `{iter_index, phase, text}`
    (for iter > 0)
  - `iteration phase="reflect"` (lines 155-166): `{iter_index, phase,
    score, needs_revision, critique_summary, text}`
  - `algo_end` (lines 181-187): `{iterations, converged}`
- `apps/dashboard/operad_dashboard/routes/iterations.py` — route shape.
- `apps/frontend/src/components/charts/{convergence-curve,iteration-progression}.tsx`.
  Both already exist; we compose them.
- `apps/frontend/src/layouts/selfrefine.json` — current shape.
- `INVENTORY.md` §7 (SelfRefine).

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/selfrefine/selfrefine-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/selfrefine/iteration-ladder.tsx`
  (the new triplet ladder view)

Edit:

- `apps/frontend/src/layouts/selfrefine.json` — fill the per-algo tabs.
- `apps/frontend/src/components/algorithms/selfrefine/registry.tsx`.

## Tab structure

```
[ Overview ] [ Iterations ] [ Convergence ] [ Agents ] [ Events ] [ Graph ]
```

(Reflections is folded into Iterations; the existing layout had a
separate tab and the user spec says to favor density.)

### Overview

```
─── status strip ─────────────────────────────────
[ ● ended | live ]   max_iter 5   iters used 3   converged ✓   final score 0.82

─── final answer card (large) ────────────────────
The last refine output, Markdown-rendered.
[ Open generator's last child run → /agents/:hash/runs/:final ]

─── score trajectory (mini) ─────────────────────
ConvergenceCurve sized small; click → switches to Convergence tab.
```

### Iterations (the ladder)

`IterationLadder` is the new view. Vertical stack of triplets:

```
┌─ iter 1 ────────────────── score 0.51 → 0.62 ──┐
│                                                 │
│ Generate (or refine, if iter > 0):              │
│ [Markdown text of the new draft]                │
│                                                 │
│ Reflect:                                        │
│ Critique summary:                                │
│ "Add concrete examples; tighten the conclusion" │
│ Score: 0.62  Needs revision: yes                │
│                                                 │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─ iter 2 ────────────────── score 0.62 → 0.74 ──┐
…
```

- The score delta arrow shows positive in green, negative in red.
- The reflection's `critique_summary` is quoted.
- Each card is collapsible (default expanded for iter ≤ 3, collapsed
  for older iters).
- A side rail on the left shows the threshold; iters that crossed
  threshold are tagged "converged here".
- URL `?iter=N` deep-links.
- Clicking a card → opens the synthetic children for that iteration
  (generator/refiner + reflector) in a side panel.

### Convergence

`ConvergenceCurve` (existing) extended to:
- Plot the threshold as a horizontal reference line.
- Mark the converged iteration with a `<ReferenceLine>` and label.
- Plot `needs_revision = false` iterations with a different marker.

### Agents

Universal. Synthetic children alternate (generator → reflector → refiner
→ reflector → ...); default `groupBy: "hash"` collapses cleanly.

## Design alternatives

### A1: Iteration density

- **(a)** Triplet card per iteration with quote-style critique
  (recommended).
- **(b)** Three-column row (generate / reflect / refine) — like Debate.
  **Reject:** SelfRefine is sequential (refine reads reflection); the
  card-with-quote shape reads better.

### A2: Reflections-as-separate-tab vs folded

- **(a)** Folded into Iterations (recommended; user spec favors density).
- **(b)** Separate "Reflections" tab (current layout). **Reject.**

## Acceptance criteria

- [ ] Tabs:
  `Overview · Iterations · Convergence · Agents · Events · Graph`.
- [ ] Overview surfaces final-answer card with deep-link.
- [ ] Iterations tab renders the ladder; older iters collapsed by
  default; URL pinning works.
- [ ] Convergence tab shows curve + threshold + converged marker.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `iteration-ladder.test.tsx` (collapsing, score delta arrow,
  pinning).
- **Layout schema:** `selfrefine.json` validates.
- **Manual smoke:** any SelfRefine run.

## Out of scope

- Backend changes.
- Universal tabs.

## Hand-off

PR body with checklist + screenshots of Iterations and Convergence.
