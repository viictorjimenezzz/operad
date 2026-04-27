# 12 — Algorithm: AutoResearcher

**Stage:** 3 (parallel; depends on Briefs 01, 02, 14, 15)
**Branch:** `dashboard-redesign/12-algo-autoresearcher`
**Subagent group:** C (Algos-narrative)

## Goal

AutoResearcher runs `n` parallel attempts, each `(plan → retrieve →
reason → critique → reflect → reason)*` until threshold or max_iter.
The view should make the parallel attempts visible (a swimlane), surface
the *plan* for each attempt as a first-class artifact, and let the user
drill into any single attempt or compare across attempts.

The plan and `attempt_index` extensions are in Brief 14.

## Read first

- `operad/algorithms/autoresearch.py` — `_one_attempt` lines 132-190;
  `run` lines 192-235. Currently emits:
  - `algo_start` (lines 196-205): `{n, max_iter, threshold}`
  - `iteration phase="reason"` after first draft (lines 142-146)
  - `iteration phase="reflect"` and `phase="reason"` per refinement
    iter (lines 160-189) — `{iter_index, phase, score}`
  - `algo_end` (lines 219-225): `{score}` (best across attempts)
- After Brief 14 lands, payloads gain:
  - `attempt_index` on every iteration
  - new event kind `"plan"`: `{attempt_index, plan: ResearchPlan.dump()}`
- `apps/frontend/src/components/charts/{convergence-curve, iteration-progression}.tsx`.
- `INVENTORY.md` §7 (AutoResearcher).
- `00-CONTRACTS.md` §5.2 (the new fields).

## Files to touch

Create:

- `apps/frontend/src/layouts/auto_researcher.json` (Brief 02 created
  the skeleton; this brief fills the per-algo tabs).
- `apps/frontend/src/components/algorithms/auto_researcher/` (new):
  - `index.ts`
  - `registry.tsx`
  - `auto-researcher-detail-overview.tsx`
  - `plan-card.tsx` (renders a `ResearchPlan` Markdown-friendly)
  - `attempts-swimlane.tsx`
- `apps/frontend/src/components/algorithms/registry.tsx` — add the
  sub-registry to the spread.

## Tab structure

```
[ Overview ] [ Plan ] [ Attempts ] [ Best answer ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ────────────────────────────────
[ ● ended ]  attempts 3  max_iter 2  threshold 0.80  best score 0.84
wall 1m 30s  total cost $0.21

─── score-vs-iteration (per-attempt overlay) ────
A multi-line chart, one line per attempt, x = iter_index, y = score,
threshold drawn as a horizontal reference line. Click an attempt's
line → switches to Attempts tab pinned to that attempt.

─── best-attempt summary ───────────────────────
Attempt #2 reached score 0.84 at iter 1.
Plan: "research the Q from biology, policy, and economic angles"
[ View full plan → tab Plan ]
[ View final answer → tab Best answer ]
```

### Plan

One `PlanCard` per attempt (or just one when n=1). Layout:

```
─── attempt #1 plan ───────────────────────────
[ Markdown render of ResearchPlan structure ]
- biology_question: "..."
- policy_question:  "..."
- economic_question: "..."

retrieved evidence (compact):
  - "doc#3: 'colony collapse correlates with neonicotinoid use…'"
  - "doc#7: 'EU bans on neonicotinoids reduced collapses by 18%…'"
  - "doc#11: 'rebuilding apiaries cost $2-5K per hive…'"
[ Open each retriever child → /agents/:hash/runs/:retriever_runId ]
```

Plans are sourced from the new `plan` algo_event (Brief 14). When a
run predates Brief 14, the Plan tab shows an empty state and a note.

### Attempts (the swimlane)

Vertical swim per attempt:

```
─── attempt #1 (best, ended at iter 1, score 0.84) ──
  iter 0: reason  | score 0.71
  iter 1: reflect | needs_revision = true
  iter 1: reason  | score 0.84  ← converged

─── attempt #2 (ended at iter 2, score 0.62) ──
  iter 0: reason  | score 0.55
  iter 1: reflect | needs_revision = true
  iter 1: reason  | score 0.62  ← max_iter reached

─── attempt #3 (ended at iter 1, score 0.78) ──
  …
```

Each row in a swim links to its synthetic child run. URL
`?attempt=N` pins one swim.

When `attempt_index` is missing (legacy runs), all iterations land
under "attempt unknown" and the empty-state explains the upgrade
needed.

### Best answer

The final selected answer (the algo_end's best). Markdown-rendered,
with the deep-link to its synthetic-child reasoner run.

### Agents

Universal. AutoResearcher invokes Planner / Retriever / Reasoner /
Critic / Reflector. Default `groupBy: "hash"` collapses cleanly into
five rows. Override (in `auto_researcher.json`):

```json
"agents": {
  "type": "AgentsTab",
  "props": {
    "runId": "$context.runId",
    "groupBy": "hash",
    "extraColumns": ["attempt_index"]
  }
}
```

`extraColumns` here requires the `AgentsTab` to expose
`attempt_index` from the synthetic children's `parent_run_metadata`
or by walking the `iteration` events that reference each child by
timestamp. Brief 15 covers the API; this brief consumes it.

## Design alternatives

### A1: Plan presentation

- **(a)** Markdown-rendered structured fields (recommended; ResearchPlan
  is a Pydantic model).
- **(b)** Raw JSON dump. **Reject:** ugly.
- **(c)** A "decomposed-question" visualization (concentric circles).
  **Reject:** too clever for the data shape.

### A2: Multi-attempt comparison

- **(a)** Overlay all attempts on a single chart (Overview).
- **(b)** Side-by-side panels per attempt. Tab Attempts already does
  this.
- **(c)** Compare drawer (Q3 says skip).

### A3: When n=1

- **(a)** Hide the swim header (recommended).
- **(b)** Always show the swim. **Reject:** clutters the view for the
  most common case.

## Acceptance criteria

- [ ] Tabs:
  `Overview · Plan · Attempts · Best answer · Agents · Events · Graph`.
- [ ] Overview score-vs-iteration overlay; click attempt-line →
  Attempts tab pinned.
- [ ] Plan tab renders Markdown-shaped ResearchPlan for each attempt,
  plus retrieved-evidence summary.
- [ ] Attempts swimlane with per-attempt rows, deep-links per row.
- [ ] Best answer surfaces final answer with Markdown.
- [ ] When `attempt_index` is missing (legacy), empty-states explain.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `attempts-swimlane.test.tsx`, `plan-card.test.tsx`.
- **Layout schema:** `auto_researcher.json` validates.
- **Manual smoke:** if no example exists, hand-craft a 2-attempt
  AutoResearcher run for testing.

## Out of scope

- Backend changes (Brief 14).
- Universal tabs (Brief 15).
- Other algorithms.

## Hand-off

PR body with checklist + screenshots of Overview, Plan, Attempts.
