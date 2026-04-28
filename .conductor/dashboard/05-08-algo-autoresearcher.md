# 05-08 AutoResearcher — plan, attempts, best

**Branch**: `dashboard/algo-autoresearcher`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`
**Estimated scope**: medium

## Goal

Replace `apps/frontend/src/layouts/auto_researcher.json` with:
`Plan · Attempts · Best · Agents · Events`.

The AutoResearcher loops `Planner → Retriever → Reasoner → Critic →
Reflector` wrapped in best-of-N. The view should make this loop
obvious.

## Files to touch

- `apps/frontend/src/layouts/auto_researcher.json` — replace.
- New:
  `apps/frontend/src/components/algorithms/auto_researcher/plan-tab.tsx`.
- New:
  `apps/frontend/src/components/algorithms/auto_researcher/attempts-tab.tsx`.
- New:
  `apps/frontend/src/components/algorithms/auto_researcher/best-tab.tsx`.
- Tests.
- `apps/frontend/src/components/algorithms/registry.tsx`.

## Contract reference

`00-contracts.md` §11.

## Implementation steps

### Plan tab

Render the `ResearchPlan` from the first `iteration` event with
`phase=plan`. Show plan steps as a numbered list with status icons
(planned/in-progress/done).

### Attempts tab

Swimlane: rows = attempts, columns = phases (`plan ·
retrieve · reason · critique · reflect`). Each cell shows a small
markdown preview of the phase output and the phase score.

Click a cell → side drawer with full output.

### Best tab

Render the best attempt's final reasoning + answer + confidence.
Pull from `algorithm_terminal_score` and the corresponding attempt's
events.

## Acceptance criteria

- [ ] AutoResearcher runs render the new tab strip.
- [ ] Plan tab shows the research plan steps.
- [ ] Attempts swimlane shows the right phases per attempt.
- [ ] Best tab shows the winning attempt summary.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Hover over an attempt row → highlight the same row across phases
  for visual flow.
- A "phase failures" filter on Attempts that highlights cells with
  errors.
