# 05-09 TalkerReasoner — tree, transcript, decisions

**Branch**: `dashboard/algo-talker-reasoner`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02`, `02-05`
**Estimated scope**: medium

## Goal

Replace `apps/frontend/src/layouts/talker_reasoner.json` with:
`Tree · Transcript · Decisions · Agents · Events`.

TalkerReasoner interleaves chat (Talker) and reasoning (Reasoner)
based on a router. The story is the per-turn router decision tree.

## Files to touch

- `apps/frontend/src/layouts/talker_reasoner.json` — replace.
- New:
  `apps/frontend/src/components/algorithms/talker_reasoner/tree-tab.tsx`.
- New:
  `apps/frontend/src/components/algorithms/talker_reasoner/transcript-tab.tsx`.
- New:
  `apps/frontend/src/components/algorithms/talker_reasoner/decisions-tab.tsx`.
- Tests.
- `apps/frontend/src/components/algorithms/registry.tsx`.

## Contract reference

`00-contracts.md` §11.

## Implementation steps

### Tree tab

Per-turn decision tree: each turn is a node with two child branches
(`talker` / `reasoner`); the chosen branch is highlighted, the
unchosen is dimmed. Layout: top-down tree.

### Transcript tab

Chat-style rendering. Each turn:
- User input (right-aligned bubble with user icon).
- Talker / Reasoner output (left-aligned bubble; identity dot per
  agent path; markdown content).

### Decisions tab

`RunTable` with columns: `turn · router_choice (kind:"pill") ·
router_confidence (kind:"score") · final_response_preview
(kind:"diff") · langfuse →`.

## Acceptance criteria

- [ ] TalkerReasoner runs render the new tab strip.
- [ ] Tree tab shows per-turn branches.
- [ ] Transcript tab is chat-styled.
- [ ] Decisions tab uses `RunTable`.
- [ ] `pnpm test --run` passes.

## Stretch goals

- Tree tab supports collapse/expand of subtrees.
- Add a "router confidence histogram" mini-panel showing distribution
  across turns.
