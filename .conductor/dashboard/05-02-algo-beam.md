# 05-02 Beam — leaderboard, candidates, histogram

**Branch**: `dashboard/algo-beam`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02` (RunTable cell kinds), `02-05` (KPIs)
**Estimated scope**: small

## Goal

Replace `apps/frontend/src/layouts/beam.json` with a Beam-shaped
view: `Leaderboard · Candidates · Score histogram · Agents · Events`.

## Why this exists

A Beam run produces N candidates and selects top-K. The user wants
to see "the top-K story": who ranked, where the cut-off lies,
where each candidate landed.

## Files to touch

- `apps/frontend/src/layouts/beam.json` — replace.
- New: `apps/frontend/src/components/algorithms/beam/leaderboard-tab.tsx`.
- New: `apps/frontend/src/components/algorithms/beam/score-histogram-tab.tsx`.
- New: tests.
- `apps/frontend/src/components/algorithms/registry.tsx` — register.

## Contract reference

`00-contracts.md` §3 (palette), §5 (`RunTable.score`), §11.

## Implementation steps

### Step 1 — Layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "leaderboard", "label": "Leaderboard" },
      { "id": "candidates", "label": "Candidates" },
      { "id": "histogram", "label": "Score distribution" },
      { "id": "agents", "label": "Agents", ... },
      { "id": "events", "label": "Events", ... }
    ]
  }
}
```

### Step 2 — `BeamLeaderboardTab`

Top-K candidates ordered by score. Use `RunTable` with columns:
`rank · score (kind:"score") · text_preview (kind:"diff") ·
selected (kind:"pill" "✓" if surviving K) · langfuse →`. Above the
table, a sticky "K = 5 of 12" stat. Below, a chip "show all
candidates" expands to render the full list.

### Step 3 — `BeamScoreHistogramTab`

Score distribution as a binned histogram (10 bins by default,
configurable). Mark the K-cutoff with a vertical line. Use
`paletteIndex(class)` for the bar color (categorical Sweep palette
slot for Beam stays consistent across screens).

### Step 4 — Candidates tab

Reuse existing `BeamCandidateChart` (`charts/beam-candidate-chart.tsx`)
for the scatter (score vs latency) — already implemented; just wire
into the new layout.

## Acceptance criteria

- [ ] Beam runs render the new tab strip.
- [ ] Leaderboard shows the top-K with score bars and the cutoff
  callout.
- [ ] Score histogram renders with K cutoff line.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Click a candidate row in the leaderboard → opens its synthetic
  child run in a side drawer (without leaving the page).
- Toggle "lower-is-better" inverts the histogram and leaderboard
  order.
- Highlight ties: candidates within ε of each other share a faint
  outline.
