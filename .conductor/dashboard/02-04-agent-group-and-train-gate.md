# 02-04 Agent-group chrome and Training-tab gate

**Branch**: `dashboard/group-chrome-and-train-gate`
**Wave**: Sequence 2, parallel batch
**Dependencies**: none
**Estimated scope**: small

## Goal

Two surgical fixes that the user explicitly named:

1. The "Train" tab leaks into non-trainable agents (e.g.
  `research_analyst`) because the gate fires on
   `metrics?.best_score != null`. Fix the gate.
2. Rename the tab label from "Train" to "Training" everywhere. The
  underlying URL stays `/agents/<hash>/train` for now (URL changes
   are out of scope; only the visible label changes).

## Why this exists

§2 of `00-contracts.md` mandates the new gate. The old gate fires on
any algorithm-emitting score, which is wrong: a `Beam` run produces a
`best_score` for an agent that has no trainable parameters.

## Files to touch

- `apps/frontend/src/dashboard/pages/AgentGroupPage.tsx:38-41` — fix
the `showTrain` calculation.
- `apps/frontend/src/components/agent-view/page-shell/agent-group-tabs.tsx:22-23` —
change the tab label to `"Training"`.
- `apps/frontend/src/dashboard/pages/AgentGroupTrainTab.tsx` — rename
any user-visible "Train" string to "Training" (file/component name
may stay; this is a label-only change). Drop the `Promote to training run` button (§14: monitor-only).

## Contract reference

`00-contracts.md` §2 (training gate), §14 (monitor-only).

## Implementation steps

### Step 1 — Gate fix

`AgentGroupPage.tsx:38`:

```ts
const showTraining =
  detail.is_trainer ||
  (meta.data?.trainable_paths.length ?? 0) > 0;
```

Drop the third clause `detail.runs.some((run) => run.metrics?.best_score != null)`.

Variable name flips from `showTrain` to `showTraining` for clarity.

### Step 2 — Tab label rename

In `agent-group-tabs.tsx`:

```ts
if (options.showTraining) {
  tabs.splice(3, 0, { to: `${base}/train`, label: "Training" });
}
```

The URL `/train` is preserved — the brief that touches routes is
01-03; pure label change here. The `options.showTrain` prop
becomes `options.showTraining`.

### Step 3 — Drop control buttons

In `AgentGroupTrainTab.tsx:65-75`:

```tsx
toolbar={
  trainableCount > 0 ? (
    <Button size="sm" variant="ghost" disabled
            title="Coming soon - see the Training rail">
      Promote to training run
    </Button>
  ) : null
}
```

Delete this `toolbar`. The button does nothing today and violates
monitor-only (§14).

## Design alternatives

1. **Rename the URL too: `/training`.** Recommendation: defer to a
  future PR. Touching routes invalidates bookmarks and is out of
   this brief's scope.
2. **Hide the tab entirely vs gray it out.** Recommendation: hide.
  Greying creates the same "what's there?" confusion the user
   complained about.

## Acceptance criteria

- On `research_analyst` (no trainable parameters,
`algorithm_terminal_score` may exist), the Training tab is **not**
visible.
- On a trainable agent (example 03 / 04), the Training tab is
visible and labeled "Training".
- No `Promote to training run` button on the Training tab.
- `pnpm test --run` passes.

## Test plan

- Update `AgentGroupPage.test.tsx` (create if absent): one fixture
with `metrics.best_score=0.8` and no `trainable_paths` →
`showTraining=false`; another with `trainable_paths=["role"]` →
`showTraining=true`.
- Manual: navigate to `research_analyst` and verify Training is
absent.

## Out of scope

- The Training tab content rebuild (Sequence 3).
- Renaming the URL to `/training`.
- Adding monitor-friendly actions (none planned).

## Stretch goals

- Surface a chip on the Training tab label showing the count of
trainable parameters (`Training (3)`).
- When the agent is also a trainee in a Trainer run, add a small
Trainer-class color dot next to the tab label, hinting at the
optimizer that's mutating it.

