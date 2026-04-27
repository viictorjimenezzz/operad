# 07 — Algorithm: Debate

**Stage:** 3 (parallel; depends on Briefs 01, 02, 15)
**Branch:** `dashboard-redesign/07-algo-debate`
**Subagent group:** C (Algos-narrative)

## Goal

Make the Debate view about *the discourse*. Each round is a 3-way
conversation (proposers → critic → synthesizer). The view should read
like a transcript, with score evolution as a sidebar context. Final
synthesized `Answer` is the artifact.

## Read first

- `operad/algorithms/debate.py` — `Debate.run()` at lines 79-158.
  Events:
  - `algo_start` (lines 83-88): `{proposers, rounds}`
  - `round` per round (lines 121-134): full `proposals[]` (each is a
    `Proposal` model dump), `critiques[]` (each is a `Critique` dump),
    `scores[]` (per-critique).
  - `algo_end` (lines 142-148): `{rounds}`. The actual `Answer` is the
    return value, available via the synthesizer's synthetic child run's
    output.
- `apps/dashboard/operad_dashboard/routes/debate.py:51-58` — returns
  rounds with full proposal+critique payloads.
- `apps/frontend/src/components/charts/debate-round-view.tsx`,
  `debate-transcript.tsx`, `debate-consensus-tracker.tsx` — existing
  components.
- `apps/frontend/src/layouts/debate.json` — current shape.
- `INVENTORY.md` §6 (`Proposer`, `DebateCritic`, `Synthesizer` schemas)
  and §7 (Debate description).

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/debate/debate-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/debate/debate-rounds-tab.tsx`
- `apps/frontend/src/components/algorithms/debate/synthesis-card.tsx`
- `apps/frontend/src/components/algorithms/debate/round-card.tsx`

Edit:

- `apps/frontend/src/layouts/debate.json` — fill per-algo tabs.
- `apps/frontend/src/components/algorithms/debate/registry.tsx` — register.

## Tab structure

```
[ Overview ] [ Rounds ] [ Consensus ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ─────────────────────────────────
[ ● ended ]  rounds 3   proposers 3   wall 1m 12s   total cost $0.018

─── synthesis card (large, top of the page) ─────
Synthesized answer
[ Markdown rendering of synthesized Answer.text ]
[ Open synthesizer run → /agents/:hash/runs/:synth_runId ]

─── consensus tracker (mini) ────────────────────
Round 1 → 2 → 3 score progression. Mean score per round, plus
each proposer's score line (so the user can see who's improving).

─── topic card (small) ──────────────────────────
"<DebateTopic.topic — Markdown>"
```

### Rounds

The transcript view. One `RoundCard` per round, vertically stacked:

```
─── Round 1 ─────────────────────────────────────
┌── Proposer A ──────────┬── Proposer B ──────────┬── Proposer C ──────────┐
│ Proposal text          │ Proposal text          │ Proposal text          │
│ (Markdown)             │                        │                        │
│                        │                        │                        │
│ Critic's score: 0.61   │ Critic's score: 0.74   │ Critic's score: 0.52   │
│ ─ critique excerpt ─   │ ─ critique excerpt ─   │ ─ critique excerpt ─   │
│ "needs more detail"    │ "good but tangential"  │ "off-topic"            │
└────────────────────────┴────────────────────────┴────────────────────────┘
[ Open critic run for round 1 → /agents/:hash/runs/:critic_r1 ]
```

A pinned bar at the top of the Rounds tab shows the current round
(URL `?round=2` deep-links). Sticky on scroll.

When a round is clicked, expand inline to show the full critic
response (not just the excerpt) and full proposal text.

### Consensus

Renders the existing `DebateConsensusTracker` chart (per-round mean
agreement). Add a new view: a strip of three boxes showing per-proposer
score evolution across rounds (Markdown column for the proposal at
each round under each box). When proposers' scores converge, the
strip visually narrows. Highlight the proposer with the highest score
in the final round (the basis for the synthesized answer).

### Agents

Universal tab. For Debate, default `groupBy: "hash"` is right —
the user sees Proposer instance ×3, Critic ×R, Synthesizer ×1.

## Design alternatives

### A1: Per-round layout

- **(a)** 3-column proposer cards above a wide critic strip
  (recommended for ≤4 proposers).
- **(b)** Tabbed-per-proposer (one tab per proposer, scrolling rounds).
  **Reject:** loses the "rounds advance" rhythm.
- **(c)** A sequence diagram (proposer→critic arrows). **Reject:** the
  shape is fixed; Mermaid is overkill.

### A2: When to expand a round

- **(a)** Click anywhere on the round card to expand (recommended).
- **(b)** A chevron in the corner. **Reject:** poor click target.
- **(c)** Always-expanded. **Reject:** fails for ≥5 rounds.

### A3: Synthesis card placement

- **(a)** Top of Overview, big (recommended). It's the answer.
- **(b)** Bottom of the Rounds tab. **Reject:** buries the artifact.

## Acceptance criteria

- [ ] Tabs render: `Overview · Rounds · Consensus · Agents · Events · Graph`.
- [ ] Overview surfaces the synthesis card with Markdown rendering and
  a deep-link to the synthesizer's synthetic child run.
- [ ] Rounds tab shows one RoundCard per round, with proposer
  proposals + critic scores + critique excerpts.
- [ ] URL `?round=N` deep-links and pins the round indicator.
- [ ] Consensus tab shows mean score per round + per-proposer lines
  with a converged-proposer highlight.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `round-card.test.tsx`, `synthesis-card.test.tsx`,
  `debate-rounds-tab.test.tsx` covering 3-round fixture.
- **Layout schema:** `debate.json` validates.
- **Visual:** screenshot per tab against a 3-round Debate run (compose
  one for testing if no example exists).

## Out of scope

- Backend changes (the round payload is already complete).
- Per-round drill-down to per-message LLM calls (use the universal
  Agents tab).

## Hand-off

PR body with checklist + per-tab screenshots. Cite file:line evidence
for each AC item.
