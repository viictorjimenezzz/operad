# 3-2 — Debate bespoke page

> **Iteration**: 3 of 4. **Parallel slot**: 2.
> **Owns**: the Debate layout JSON, debate-specific chart components,
> and a NEW backend route for round details.
> **Forbidden**: other layouts/components, generic infra.

## Problem

The current `debate.json` layout is skeletal: it shows per-round score
bars and nothing else. `Debate` is one of operad's most narratively
interesting algorithms — N proposers exchange arguments, a critic
scores each round, and a final synthesizer produces an answer. The
*content* of the debate (the actual proposals and critiques) is the
whole point.

Today the dashboard:

- Shows `summary.rounds` (aggregate scores per round).
- Does not show proposal text.
- Does not show critic feedback.
- Does not show the final synthesis.
- Does not show convergence-over-rounds (did agreement increase?).

## Scope

### Owned files

- `apps/frontend/src/layouts/debate.json`
- `apps/frontend/src/shared/charts/debate-round-view.tsx` (extend or
  replace).
- New: `apps/frontend/src/shared/charts/debate-transcript.tsx` —
  per-round proposal/critique viewer.
- New: `apps/frontend/src/shared/charts/debate-consensus-tracker.tsx` —
  line/area chart of agreement over rounds (variance-based metric).
- New: `apps/dashboard/operad_dashboard/routes/debate.py` — aggregation
  endpoint exposing per-round proposals + critiques.
- Tests.

### Forbidden files

- Other layouts and components.
- Generic infra (2-2's domain) and run list (2-1's domain).
- `app.py`, `runs.py` — only add new route file under `routes/`.

## Direction

### Investigate the runtime

Read `operad/algorithms/debate.py` to learn what events it emits.
Likely shape (verify):

- `algo_event` `kind="round"` payload:
  ```
  {
    "round_index": int,
    "proposers": [{"id": str, "argument": str}],
    "critic_scores": {proposer_id: score},
    "winning_proposer_id": str | None,
  }
  ```
- `algo_event` `kind="synthesis"` payload at the end:
  ```
  {"final_answer": str, "rationale": str}
  ```

If the runtime doesn't emit this rich a payload, document the gap.
You can implement against a synthetic fixture for tests, then file a
follow-up to extend `Debate` to emit the missing fields.

### Backend: `routes/debate.py`

Aggregate per-run round data:

- `GET /runs/{id}/debate.json` →
  `{rounds: [{round_index, proposers, critic_scores, winning}], synthesis}`.
- `GET /runs/{id}/debate.sse` for live updates.

Match the style of `routes/fitness.py` and `routes/drift.py`.

### `<DebateTranscript />` component

For each round:

- Header row: round index, winning proposer (badge), agreement metric.
- Per-proposer card: proposer id, argument text (markdown if multi-line),
  critic score visualized as a small bar.
- Expandable "critic feedback" section per proposer.

Make it scannable: one card per round, expandable to show full text.
Default to first round expanded.

### `<DebateConsensusTracker />`

Compute a per-round "agreement" metric (e.g. score variance) and plot
it. Optional: also show a "winning proposer over rounds" sparkline
that tells the user whether one voice dominated or the winner shifted.

### `<DebateRoundView />` (existing) — keep as the score-bar summary

It's fine as a top-level glance card. Move it into the Overview tab
of the layout; the new transcript becomes a separate tab.

### Layout

```
trainer.json tabs:
  - Overview: round-view summary + consensus tracker
  - Transcript: full round-by-round dialogue
  - Final: synthesis card with rationale
  - Graph
  - Events
```

(That's `debate.json`, sorry — example shape, not a literal copy.)

## Acceptance criteria

1. Run a Debate demo (find one in `examples/` or compose a small
   one offline). Navigate to its run page → see proposers, critique
   text, scores, final synthesis.
2. Transcript tab shows actual proposal text, not just scores.
3. Consensus tracker chart renders with reasonable scale.
4. Tests cover: route serialization, transcript renders with empty/
   single/multi rounds, consensus calculation.

## Dependencies & contracts

### Depends on

- 1-1, 1-2, 2-2 (renderer + backfill), 2-3 (pin button), 3-5
  (Langfuse card).

### Exposes

- `<DebateTranscript />` may be reused by 3-3 / 3-4 if their
  algorithms have similar "log of textual outputs" needs (probably
  not, but document the API).
- `/runs/{id}/debate.json|.sse` endpoints.

## Risks / non-goals

- Don't try to render the agent graph differently for Debate — it's
  the same graph rendering as everywhere else.
- Don't add a "vote on the round" interactive feature; this is a
  trace viewer.
- Don't change the algorithm; just the dashboard view.

## Direction notes / SOTA hints

- Markdown rendering: `react-markdown` (check lockfile).
- Long-text panels: use shadcn's `<ScrollArea />` if available.
- Variance metric: `Math.sqrt(Σ(score - mean)² / N)`; agreement is
  `1 - variance / max_possible_variance`.

## Verification checklist

- [ ] Demo end-to-end shows transcript.
- [ ] Backend route tests pass.
- [ ] Frontend tests pass.
- [ ] Empty-round case renders gracefully (e.g. live-streaming run
      where round 0 hasn't completed yet).
