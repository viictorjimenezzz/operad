# 05-03 Debate — rounds, transcript, consensus

**Branch**: `dashboard/algo-debate`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`
**Estimated scope**: small

## Goal

Replace `apps/frontend/src/layouts/debate.json` with:
`Rounds · Transcript · Consensus · Agents · Events`. Every component
already exists (`DebateRoundView`, `DebateTranscript`,
`DebateConsensusTracker`) — this brief is mostly layout wiring with
one polish pass.

## Why this exists

Today's debate layout reuses the generic Overview/Events template;
the user wants per-class structure that surfaces the rounds and the
consensus arc.

## Files to touch

- `apps/frontend/src/layouts/debate.json` — replace.
- `apps/frontend/src/components/algorithms/debate/` — small wrapper
  components if needed to consume the layout's `runId`/`source`
  contract. Reuse the existing chart components 1:1.
- `apps/frontend/src/components/algorithms/registry.tsx` — register.

## Contract reference

`00-contracts.md` §11.

## Implementation steps

### Layout

```json
"page": {
  "type": "Tabs",
  "props": {
    "tabs": [
      { "id": "rounds", "label": "Rounds" },
      { "id": "transcript", "label": "Transcript" },
      { "id": "consensus", "label": "Consensus" },
      { "id": "agents", "label": "Agents", ... },
      { "id": "events", "label": "Events", ... }
    ]
  }
}
```

Each tab body wraps the existing chart component:

- `rounds` → `DebateRoundView` (render bars per round).
- `transcript` → `DebateTranscript` (markdown side-by-side per round).
- `consensus` → `DebateConsensusTracker` (line chart of agreement
  over rounds).

## Acceptance criteria

- [ ] Debate runs render the new tab strip.
- [ ] All three bespoke tabs source from
  `/runs/.../debate.json` (or the equivalent existing endpoint;
  reuse the data source already used by `DebateRoundView`).
- [ ] `pnpm test --run` passes; layout JSON parse passes.

## Stretch goals

- Add a "winning argument" callout in Rounds that highlights the
  proposal with the highest final synthesis score.
- Allow the Transcript tab to filter to just one debater's
  contributions.
