# 05-11 Universal `InvocationsTab` element

**Branch**: `dashboard/universal-invocations-tab`
**Wave**: Sequence 5, parallel batch
**Dependencies**: `01-02` (RunTable cell kinds)
**Estimated scope**: medium

## Goal

Build a single universal `InvocationsTab` JSON-layout element that
every algorithm uses to render its rich invocations table with
algorithm-specific columns (per the table in
`00-contracts.md` §11). Each per-algorithm brief in this sequence
references this element from its layout JSON without duplicating
implementation.

## Why this exists

- The user wants a "rich table like the one in W&B that I can see
  the algorithm events in a way that makes sense for every
  algorithm". One element with a per-class column descriptor is the
  least-duplication design.
- §5 of `00-contracts.md` reserves the four new RunTable cell kinds
  (`param`, `score`, `diff`, `image`) that the per-algorithm column
  descriptors consume.

## Files to touch

- New: `apps/frontend/src/components/runtime/invocations-tab.tsx`.
- New: `apps/frontend/src/components/runtime/invocations-tab.test.tsx`.
- New: `apps/frontend/src/lib/invocation-columns/` —
  per-algorithm column descriptors:
  - `sweep.ts`, `beam.ts`, `debate.ts`, `evogradient.ts`,
    `trainer.ts`, `opro.ts`, `selfrefine.ts`, `auto_researcher.ts`,
    `talker_reasoner.ts`, `verifier.ts`, `default.ts`.
- `apps/frontend/src/components/runtime/dashboard-renderer.tsx` —
  register `InvocationsTab` element.

## Contract reference

`00-contracts.md` §5 (RunTable cells), §11 (element types).

## Implementation steps

### Step 1 — Component shape

```tsx
export interface InvocationsTabProps {
  runId: string;
  algorithmClass?: string | null;          // overrides auto-detection
  defaultGroupBy?: "none" | "epoch" | "round" | ...;
}

export function InvocationsTab({ runId, algorithmClass, defaultGroupBy }: ...) {
  // 1. fetch /runs/{runId}/children
  // 2. resolve column descriptor by algorithmClass (or read from summary)
  // 3. transform children -> RunRow[] using the descriptor's mapper
  // 4. render <RunTable rows={...} columns={cols} ... />
}
```

### Step 2 — Column descriptor shape

```ts
// apps/frontend/src/lib/invocation-columns/types.ts
export interface AlgorithmColumns {
  algorithmClass: string;
  columns: RunTableColumn[];                       // existing type
  rowMapper: (child: RunSummary, parent: RunSummary) => RunRow;
  defaultGroupBy?: (row: RunRow) => { key: string; label: string };
}
```

### Step 3 — Per-algorithm descriptors

`sweep.ts`:

```ts
export const sweepColumns: AlgorithmColumns = {
  algorithmClass: "Sweep",
  columns: [
    { id: "cell", label: "Cell", source: "_id", width: 90, sortable: true },
    // axis_<n> columns are produced dynamically from parent.summary.axes
    { id: "score", label: "Score", source: "score", align: "right",
      sortable: true, defaultSort: "desc" },
    { id: "latency", label: "Latency", source: "_duration", align: "right" },
    { id: "cost", label: "Cost", source: "cost", align: "right" },
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 90 },
  ],
  rowMapper: (child, parent) => ({
    id: child.run_id,
    identity: child.hash_content ?? child.run_id,
    state: child.state,
    startedAt: child.started_at,
    endedAt: child.last_event_at,
    durationMs: child.duration_ms,
    fields: {
      score: { kind: "score", value: child.metrics?.score ?? null,
               min: 0, max: 1 },
      cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
      langfuse: child.langfuse_url
        ? { kind: "link", label: "open", to: child.langfuse_url }
        : { kind: "text", value: "—" },
      // axis values come from child.metadata.axis_values:
      ...axisFields(parent, child),
    },
  }),
};
```

Repeat per algorithm following `00-contracts.md` §5.2 / §11. Use
`kind: "param"` for axis values, `kind: "score"` for scores,
`kind: "diff"` for text deltas, `kind: "pill"` for boolean
flags.

### Step 4 — Layout consumption

Per-algorithm briefs (05-01 through 05-10) reference this element:

```json
"invocations": {
  "type": "InvocationsTab",
  "props": { "runId": "$context.runId" }
}
```

When `algorithmClass` is omitted, the component infers it from
`/runs/{runId}/summary.algorithm_class`.

## Design alternatives

1. **One InvocationsTab vs per-algorithm bespoke tabs.**
   Recommendation: one universal — the user wants consistent
   interactivity (sort, filter, group, column picker), and per-algo
   columns are data, not code.
2. **Column descriptors in JS vs JSON.** Recommendation: JS — they
   include `rowMapper` (a function); a JSON schema would push that
   logic somewhere else.

## Acceptance criteria

- [ ] `InvocationsTab` resolves the right column descriptor for each
  of the 10 algorithm classes.
- [ ] When the algorithm is unknown, `default.ts` is used (renders
  basic columns: `state · run · started · duration · score`).
- [ ] Sorting, filtering, grouping, column-picking all work (these
  are RunTable features inherited by composition).
- [ ] `pnpm test --run` passes.

## Test plan

- `invocations-tab.test.tsx`: render with each fixture per algorithm
  class; assert column count and a few field values.

## Out of scope

- The per-algorithm bespoke tabs (briefs 05-01 through 05-10 own
  those layouts; they consume `InvocationsTab` from this brief).

## Stretch goals

- Saved views: when the user changes column visibility / sort / page
  size, persist a "saved view" per algorithm class in
  `localStorage`.
- Auto-derive axis columns for Sweep from `parent.summary.axes`
  (read at render time).
- Multi-row select with a sticky "Compare N" toolbar (foreshadowing
  brief `06-04`).
