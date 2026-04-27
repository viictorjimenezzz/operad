# 11 — Algorithm: VerifierAgent

**Stage:** 3 (parallel; depends on Briefs 01, 02, 15)
**Branch:** `dashboard-redesign/11-algo-verifier`
**Subagent group:** B (Algos-quant)

## Goal

VerifierAgent runs a `(generate → verify)` loop until the verifier's
score crosses a threshold. Unlike other algorithms, `VerifierAgent` is
*itself an Agent* (`Agent[Task, Answer]`), so each invocation is
*both* a top-level agent run *and* an algorithm run with the same
`run_id`. The view should make this duality clear (we're inside both an
algorithm and an agent at once) and surface the threshold prominently.

## Read first

- `operad/agents/reasoning/verifier.py` — `VerifierAgent.forward()`
lines 49-100. Events:
  - `algo_start` (lines 53-58): `{max_iter, threshold}`
  - `iteration phase="verify"` per iteration (lines 67-76):
  `{iter_index, phase, score, text}`
  - `algo_end` (lines 80-90): `{iterations, score, converged}`
- `apps/dashboard/operad_dashboard/routes/iterations.py`.
- `apps/frontend/src/components/charts/convergence-curve.tsx`,
`iteration-progression.tsx` — existing.
- `apps/frontend/src/layouts/verifier.json` — current shape.
- `INVENTORY.md` §6 (`VerifierAgent`).

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/verifier/verifier-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/verifier/verifier-iterations.tsx`

Edit:

- `apps/frontend/src/layouts/verifier.json`
- `apps/frontend/src/components/algorithms/verifier/registry.tsx`

## Tab structure

```
[ Overview ] [ Iterations ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ─────────────────────────────────
[ ● ended | live ]  threshold 0.80  max_iter 3  iters 2  converged ✓
final score 0.91   wall 14s

─── final answer card ────────────────────────────
The accepted Answer, Markdown-rendered.

─── threshold-vs-score sparkline ─────────────────
A small inline view of the score trajectory with the threshold line.
Each iter is a dot; the converged iter is starred.

─── duality note (small, advisory) ───────────────
"This is a VerifierAgent — it's both an algorithm and an agent.
You can also view it under the Agents rail at /agents/:hash/runs/:runId."
[ Open agent view → /agents/:hash/runs/:runId ]
```

The duality note is important — `VerifierAgent` is the only algorithm
that's also an Agent in the operad data model. Surfacing the cross-
link prevents user confusion.

### Iterations

Per-iter cards stacked vertically:

```
┌─ iter 1 ─────────────── score 0.62 ──┐
│ Generated:                            │
│ [Markdown of attempt]                  │
│ Verifier critique: "missing example"   │
│ Reject (below threshold).              │
└──────────────────────────────────────┘
┌─ iter 2 ─────────────── score 0.91 ──┐
│ Generated:                            │
│ [Markdown of attempt]                  │
│ Accept (>= threshold).                 │
└──────────────────────────────────────┘
```

Score column color = `--color-warn` for below-threshold,
`--color-ok` for accepted. URL `?iter=N` deep-link.

### Agents

Universal. For VerifierAgent, synthetic children = generator + verifier
per iter. Default `groupBy: "hash"` collapses to two rows (one per
inner agent class).

## Design alternatives

### A1: Iteration card density

- **(a)** Stacked cards (recommended).
- **(b)** Single horizontal strip — too cramped at 3 iterations.

### A2: How to render the duality

- **(a)** Advisory note + cross-link in Overview (recommended).
- **(b)** A dedicated "Agent view" tab. **Reject:** duplicates Brief 03.
- **(c)** Auto-redirect to the Agent rail. **Reject:** loses the
algorithm-level structure.

## Acceptance criteria

- Tabs: `Overview · Iterations · Agents · Events · Graph`.
- Overview surfaces threshold, final score, accepted answer card.
- Iterations tab shows per-iter cards with score color-coded;
threshold logic correct.
- Cross-link to `/agents/:hash/runs/:runId` works (same `runId` —
this is the duality).
- `pnpm test --run` green.

## Test plan

- **Unit:** `verifier-iterations.test.tsx`.
- **Layout schema:** `verifier.json` validates.
- **Manual smoke:** any VerifierAgent invocation.

## Out of scope

- Backend changes (none).
- Universal tabs.

## Hand-off

PR body with checklist + screenshots of Overview and Iterations.