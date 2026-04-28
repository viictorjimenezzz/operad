# 02-01 Single-invocation Overview redesign

**Branch**: `dashboard/single-invocation-overview`
**Wave**: Sequence 2, parallel batch
**Dependencies**: `01-02` (HashRow, density tokens)
**Estimated scope**: medium

## Goal

Rebuild the single-invocation Overview tab so it tells the operad
story: identity, I/O, definition, reproducibility — in that order, in
a flat layout without the "Sequential code window" complaint, and
without monitor-violating buttons (Replay, Cassette replay).

## Why this exists

- The current page (`SingleInvocationOverviewTab.tsx`) shows
  `RunStatusStrip · IOHero · NotesSection · DefinitionSection ·
  ReproducibilitySection`. The user complained the result is bubbly
  and the most operad-specific signal (the 7 hashes) is buried at the
  bottom.
- §14 of `00-contracts.md` mandates monitor-only: drop Replay /
  Cassette replay buttons.
- The composite case (e.g. `research_analyst`) needs a structural
  preview to root the user; otherwise the I/O panel feels orphaned.

## Files to touch

- `apps/frontend/src/dashboard/pages/run-detail/SingleInvocationOverviewTab.tsx` —
  reorder + rewrite.
- `apps/frontend/src/components/agent-view/overview/io-hero.tsx` —
  drop the action buttons; refactor to a 2-column borderless layout.
- `apps/frontend/src/components/agent-view/overview/definition-section.tsx` —
  remove `IdentityBlock` (the JSON dump); render `role/task/rules/
  examples/config` as a tabbed inline view (no `KeyValueGrid`).
- `apps/frontend/src/components/agent-view/overview/reproducibility-block.tsx` —
  switch to `HashRow` (from brief `01-02`).
- `apps/frontend/src/components/agent-view/overview/run-status-strip.tsx` —
  flatten into a borderless activity bar.
- `apps/frontend/src/components/agent-view/overview/notes-section.tsx` —
  optional: fold into Definition as a "Notes" sub-tab; ask first.
- New: `apps/frontend/src/components/agent-view/overview/structure-overview.tsx`
  — compact mermaid-derived flowchart for composite invocations.

## Contract reference

`00-contracts.md` §1 (identity), §3 (palette), §4 (density), §6
(HashRow), §14 (monitor-only).

## Implementation steps

### Step 1 — Page layout

```tsx
return (
  <div className="h-full overflow-auto">
    <div className="mx-auto flex max-w-[1180px] flex-col gap-4 p-4">
      <ActivityStrip dataSummary={summary.data} dataInvocations={invocations.data} />
      <IOPanel input={...} output={...} />
      <DefinitionPanel ... />
      <HashRowSection current={...} previous={...} />
      {hasComposite && <StructureOverview runId={runId} />}
    </div>
  </div>
);
```

No nested `rounded-lg border bg-bg-1` wrappers. Each section is
separated by a single `border-b border-border` rule with
`pad-y/pad-x` from tokens (§4).

### Step 2 — `ActivityStrip`

Replaces `RunStatusStrip`. Borderless flex bar:

```
[●live] · started 5m ago · duration 24m18s · 1.2k tokens · $0.04 · langfuse →
```

Identity dot + state pill + 4 metrics + 1 langfuse link. No card
wrapper. Sticky just under the breadcrumb (use `top-0 z-10` if
`overflow-auto` allows; otherwise non-sticky is fine for v1).

### Step 3 — `IOPanel`

Drop the IOHero buttons (`Replay`, `Cassette replay`, `Copy as JSON`).
Keep `Copy as JSON` if and only if it does not call any backend
mutation — it's clipboard-only, so it stays. Rebuild as a 2-column
grid (`Input | Output`), each a `FieldTree` (existing primitive)
showing Pydantic fields with descriptions. Default expansion: depth 2.

### Step 4 — `DefinitionPanel`

Replace the current `CollapsibleSection`-of-four-blocks with a single
borderless tab strip:

```
[ role | task | rules (3) | examples (2) | config ]
```

Active tab renders the content directly below in markdown / list /
key-value form as appropriate. Source: `useAgentMeta(runId, agentPath)`.
Drop the existing `IdentityBlock` (it duplicated breadcrumb data).

### Step 5 — `HashRowSection`

```tsx
<section className="space-y-2 border-t border-border pt-4">
  <Eyebrow>reproducibility</Eyebrow>
  <HashRow current={hashFromLatest(latest)} previous={hashFromPrev(previous)} />
</section>
```

`current` / `previous` are read from the latest two invocations of
the parent group (use `useAgentGroup(hashContent)` if available;
otherwise omit `previous`).

### Step 6 — `StructureOverview` (composite-only)

When the invocation is a composite (`agent_graph.nodes.length > 1`),
render a compact `mermaid`/flowchart preview at the bottom of the
page. Reuse the lightweight `agent-flow-graph.tsx` but with `fitView`
zoom-out and `nodesDraggable=false`. 280px tall. Click any node →
navigates to the Graph tab focused on that node (URL state).

If the invocation is a leaf, omit this section entirely.

## Design alternatives

1. **Merge Notes into Definition vs keep as a top-level section.**
   Recommendation: merge as a sub-tab. Top-level Notes is rare and
   eats vertical space.
2. **Activity strip as sticky vs static.** Recommendation: static for
   v1 (simpler); sticky in a stretch goal once we verify the
   `overflow-auto` ancestor permits it.
3. **`StructureOverview` always vs composite-only.** Recommendation:
   composite-only. A leaf has nothing to add over the breadcrumb.

## Acceptance criteria

- [ ] No `IdentityBlock` JSON dump on the page.
- [ ] No "Replay" or "Cassette replay" button anywhere on this page.
- [ ] `HashRow` renders the 7 hashes; chips for changed hashes show
  the warn outline.
- [ ] On example 01 (`research_analyst` single invocation), the
  Definition tab strip shows role/task/rules/examples/config and
  switches between them without re-fetching.
- [ ] On a composite invocation, the structural overview at the
  bottom is clickable and navigates to the Graph tab.
- [ ] `pnpm test --run` passes; existing
  `single-invocation-overview-tab.test.tsx` updated.
- [ ] Visual: open example 01, no nested bubbles, no dead space.

## Test plan

- Update `single-invocation-overview-tab.test.tsx` to assert on the
  new section order, the absence of monitor-violating buttons, and the
  presence of `HashRow`.
- Add a `Definition` tab strip switching test.
- Manual: examples 01-04, every invocation Overview renders cleanly.

## Out of scope

- Group Overview tab (brief `02-02`).
- Inspector Overview rewrite (brief `02-03`).
- Parameter evolution drawer (brief `03-02`).

## Stretch goals

- Add an "Open in graph" affordance on each I/O field that traces back
  to the agent that produced it (when leaf-level).
- Add a tiny `MetricSeriesChart` next to the Activity strip showing
  per-stage latency for composite invocations (uses the
  `agentInvocations` per-leaf data).
- Fold rare notes (length < 80 chars) directly into the Activity
  strip; only spawn a Notes sub-tab when notes are long.
