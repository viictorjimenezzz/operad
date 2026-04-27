# 06 — Algorithm: Beam (best-of-N)

**Stage:** 3 (parallel; depends on Briefs 01, 02, 15)
**Branch:** `dashboard-redesign/06-algo-beam`
**Subagent group:** B (Algos-quant)

## Goal

Make the Beam view about ranking N candidates and picking top-K. The
current `beam.json` has tabs `candidates / graph / events`; we
restructure to `Overview / Candidates / Histogram / Agents / Events /
Graph`. The Candidates tab is a leaderboard with judge rationale on
hover and per-candidate drill-in to the synthetic child run.

## Read first

- `operad/algorithms/beam.py` — `Beam.run()` is at lines 106-210.
  Events emitted:
  - `algo_start` (lines 110-115): `{n, top_k}`
  - `candidate` per generated candidate (lines 156-167):
    `{iter_index: 0, candidate_index, score, text}`
  - `iteration phase="prune"` or `phase="truncate"` (lines 175-185):
    `{iter_index: 0, phase, score, top_indices, dropped_indices}`
  - `algo_end` (lines 186-192): `{top_indices, top_scores}`
- `apps/dashboard/operad_dashboard/runs.py:377-386` — `RunInfo.candidates`
  aggregation. Each entry: `{iter_index, candidate_index, score, text, timestamp}`.
- `apps/dashboard/operad_dashboard/routes/iterations.py` returns iter
  events; the `phase="prune"` event tells us which indices won.
- `apps/frontend/src/components/charts/beam-candidate-chart.tsx` and
  `convergence-curve.tsx`, `iteration-progression.tsx` — existing chart
  primitives. Read them.
- `apps/frontend/src/layouts/beam.json` — current shape.
- `INVENTORY.md` §7 (Beam description), §8 (Metrics: `LLMAAJ` is the
  natural critic).

## Files to touch

Create:

- `apps/frontend/src/components/algorithms/beam/beam-detail-overview.tsx`
- `apps/frontend/src/components/algorithms/beam/beam-leaderboard.tsx`
- `apps/frontend/src/components/algorithms/beam/beam-score-histogram.tsx`
- `apps/frontend/src/components/algorithms/beam/critic-rationale-card.tsx`
  (per-candidate detail when expanded)

Edit:

- `apps/frontend/src/layouts/beam.json` — fill the per-algo tabs.
- `apps/frontend/src/components/algorithms/beam/registry.tsx` — register.

## Tab structure

```
[ Overview ] [ Candidates ] [ Histogram ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ─────────────────────────────────
[ ● ended ]   n=8   top_k=3   winner score 0.91   duration 2m 14s

─── winner card (large) ──────────────────────────
Winner: candidate #4   score 0.91   judge: LLMAAJ
"<top-k candidate text — Markdown rendered>"
[ Open synthetic child → /agents/:hash/runs/:winnerRunId ]

─── score band sparkline ─────────────────────────
A small sparkline showing all N candidate scores,
sorted, with the top-k threshold drawn as a line.

─── KPI strip (bottom) ───────────────────────────
[ score range 0.41–0.91 ]  [ top_k threshold 0.78 ]  [ judge cost $0.012 ]
```

### Candidates (the leaderboard)

A `RunTable` of candidates. Columns:

```
[●][Rank][Candidate #][Score][Text preview][Judge rationale][Cost][Latency][Run]
```

Sort default: score desc. Storage key `beam-candidates:<runId>`.

- Rank column: `1`, `2`, `3`, …; rows in `top_indices` get a star icon.
- Score: rendered as a tiny bar in the cell (width = score / max).
- Text preview: first 80 chars of `candidate.text` rendered Markdown,
  truncated with `…`.
- Judge rationale: tooltip on hover showing the LLM judge's full
  rationale (sourced from the synthetic child run of the critic — fetch
  on demand). When the run has no judge, this column is hidden.
- Run: deep-link to the synthetic child run for that candidate
  (generator's invocation).

Click a row → expands inline using `CollapsibleSection`:

```
─── candidate #4 (winner) ──────────────────────────
Generator: Reasoner (gpt-4o-mini, temp 0.7)
Cost: $0.0042   Latency: 1.4s   Judge score: 0.91

Full text:
[ Markdown rendering of candidate.text ]

Judge rationale:
[ critic_score's rationale, also Markdown ]

[ Open generator run → /agents/:hash/runs/:gen_runId ]
[ Open critic run    → /agents/:hash/runs/:critic_runId ]
```

The two "Open" buttons depend on us being able to identify which
synthetic child is the generator vs the critic. Strategy: walk
`/runs/:runId/children`, match by:
- generator children: `agent_path` ends with `Reasoner` (or whatever
  `Beam.generator.__class__.__name__` is, available via the algo's
  `algo_start.metadata` — Brief 14 ensures this is captured).
- critic children: `agent_path` ends with `Critic`.

When `iter_index == 0` is the only iteration we have (N candidates,
1 iteration), candidate index aligns with synthetic-child index in
generator order.

### Histogram

A simple `BeamCandidateChart` (existing) extended to show:

- A score histogram (bin width auto-computed).
- Top-K threshold as a vertical reference line.
- Click a bin to filter the Candidates tab to those candidates (URL
  `?score=<min>:<max>`).

### Agents (universal, no override)

The universal Agents tab works as-is for Beam: groups N synthetic
generators + N critics by `hash_content`, showing two rows: the
Reasoner instance and the Critic instance. User can ungroup.

## Design alternatives

### A1: Where to surface judge rationale

- **(a)** In a tooltip on the Candidates row + full in expanded card
  (recommended). Tooltip is glanceable; expansion is for deep dives.
- **(b)** A separate "Critic" tab. **Reject:** the rationale is inert
  without the candidate it judged.

### A2: Histogram or scatter

- **(a)** Histogram with top-K reference line (recommended).
- **(b)** Scatter of candidates by index. The scatter currently exists
  in `beam-candidate-chart.tsx`; we can keep it as a Histogram-tab
  toggle.
- **(c)** Both: tabs within the tab (Histogram / Scatter). Allowed if
  the user finds value; default to Histogram.

### A3: Beam without a judge (`judge=None`)

When `Beam(judge=None)`, scores are null. Candidates list shows by
generation order (no rank). Histogram becomes a length distribution
(text length). Mention this in the empty-state copy.

## Acceptance criteria

- [ ] Tabs render: `Overview · Candidates · Histogram · Agents · Events · Graph`.
- [ ] Overview surfaces the winner card with Markdown text and the
  generator's run deep-link.
- [ ] Candidates tab leaderboard sorts by score; top-K starred;
  expansion shows full text + judge rationale; deep-links to
  generator + critic runs work.
- [ ] Histogram tab shows the score distribution + top-K threshold;
  bin click filters the Candidates URL.
- [ ] When `judge=None`, the Candidates table hides the score column
  and the Histogram switches to a text-length distribution.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `beam-leaderboard.test.tsx` (sort, expand, deep-link),
  `beam-score-histogram.test.tsx`, `critic-rationale-card.test.tsx`.
- **Layout:** `beam.json` validates against the new schema.
- **Manual smoke:** run `examples/02_algorithm.py` against a Beam
  configuration and verify all tabs render.

## Out of scope

- Backend changes (none required — the existing payload is enough,
  except optional metadata for "which child is generator vs critic"
  which Brief 14 covers).
- Universal Agents/Events/Graph tabs (Brief 15).

## Hand-off

PR body with checklist + screenshots of Overview, Candidates expanded,
Histogram.
