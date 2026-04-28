# 05-10 Verifier — iterations, acceptance, parameters

**Branch**: `dashboard/algo-verifier`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`, `04-01`
**Estimated scope**: small

## Goal

Replace `apps/frontend/src/layouts/verifier.json` with:
`Iterations · Acceptance · Parameters · Agents · Events`.

## Why this exists

VerifierAgent loops generator + verifier until threshold or
max_iter. The story is "did the verifier accept; if not, how did the
generator change?".

## Files to touch

- `apps/frontend/src/layouts/verifier.json` — replace.
- New:
  `apps/frontend/src/components/algorithms/verifier/iterations-tab.tsx`.
- New:
  `apps/frontend/src/components/algorithms/verifier/acceptance-tab.tsx`.
- Tests.
- `apps/frontend/src/components/algorithms/registry.tsx`.

## Contract reference

`00-contracts.md` §11.

## Implementation steps

### Iterations tab

`RunTable` with columns: `iter · candidate_text (kind:"diff") ·
verifier_score (kind:"score") · accepted (kind:"pill")`. Hash-color
left rail by candidate identity.

### Acceptance tab

Histogram: 2 bins (accepted / rejected) above the threshold (vertical
line). Below, a small "acceptance rate over iterations" line plot.

### Parameters tab

`ParametersTab` with `scope="run"`.

## Acceptance criteria

- [ ] Verifier runs render the new tab strip.
- [ ] Iterations table shows per-iter candidate + score + accepted.
- [ ] Acceptance histogram has the threshold line.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Iterations tab adds a "diff vs previous" toggle showing how each
  candidate evolved from the last.
- Acceptance tab adds a "first acceptance" callout pointing at the
  iteration that crossed the threshold.
