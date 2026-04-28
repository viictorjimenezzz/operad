# 02-03 Graph inspector cleanup

**Branch**: `dashboard/graph-inspector-cleanup`
**Wave**: Sequence 2, parallel batch
**Dependencies**: `01-02` (HashRow)
**Estimated scope**: medium

## Goal

Trim the graph inspector to its monitoring essentials, fix the
"input/output side-by-side" cosmetic complaint, and convert the events
view from bubbles to a log. Concretely: 6 inspector tabs → 4; vertical
I/O label-on-top; events as a virtualized `EventRow` list; surface
Langfuse as an inline link in Overview, not a tab.

## Why this exists

- §14 of `00-contracts.md` mandates monitor-only; "Edit & run" is the
  flagrant violator.
- `tab-agent-langfuse.tsx` adds a whole tab for one link; the user
  prefers it inline in Overview.
- `tab-agent-overview.tsx`'s `KeyValueGrid` (lines 22-34) renders
  identity horizontally with empty space; the user wants
  `attr_name\nvalue` vertical.
- `tab-agent-events.tsx` renders `<li>` cards with bubbles; the user
  wants a log view with timestamps.

## Files to touch

- `apps/frontend/src/components/agent-view/graph/inspector/tab-experiment.tsx` —
  delete file (and its test `tab-experiment.test.tsx`).
- `apps/frontend/src/components/agent-view/graph/inspector/tab-agent-langfuse.tsx` —
  delete file.
- `apps/frontend/src/components/agent-view/graph/inspector/inspector-shell.tsx` —
  reduce `EDGE_TABS` to 4 entries (Overview, Invocations, Prompts,
  Events); remove the `experiment` and `langfuse` cases from the
  `Body` switch; remove imports.
- `apps/frontend/src/stores/index.ts` (or wherever
  `GraphInspectorTab` is defined) — drop `experiment` and `langfuse`
  from the union; update default tab if needed.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-agent-overview.tsx` —
  rewrite to vertical sections; add inline Langfuse link.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-agent-events.tsx` —
  rewrite to log style using `EventRow`.
- `apps/frontend/src/components/agent-view/graph/inspector/inspector-shell.tsx`
  header — add an inline `langfuse →` chip when
  `meta.langfuse_search_url` is present (read from
  `useAgentMeta(runId, agentPath)`).

## Contract reference

`00-contracts.md` §14 (monitor-only), §6 (HashRow), §3 (palette).

## Implementation steps

### Step 1 — Delete tabs

Remove the `tab-experiment.tsx` and `tab-agent-langfuse.tsx` files and
their imports in `inspector-shell.tsx`. Drop `experiment` and
`langfuse` from `GraphInspectorTab` and any URL-state handling tied
to them.

### Step 2 — Inspector header langfuse chip

In `inspector-shell.tsx`, the header currently has the agent class
and pill. Add an inline chip:

```tsx
{meta?.langfuse_search_url ? (
  <a
    href={meta.langfuse_search_url}
    target="_blank"
    rel="noopener noreferrer"
    className="ml-2 inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
  >
    langfuse <ExternalLink size={11} />
  </a>
) : null}
```

### Step 3 — Tab Overview rewrite

Replace `KeyValueGrid` (lines 22-34) with vertical sections, each
labeled by an `Eyebrow` and rendering the value below. Sections in
order:

1. **identity** — class, kind, agent path (mono), `HashRow` (only
   `hash_content` chip + tooltip showing all related hashes).
2. **input** — schema name + `FieldTree(input_schema)`, default depth 2.
   Label-on-top.
3. **output** — schema name + `FieldTree(output_schema)`, default
   depth 2.
4. **role** — markdown.
5. **task** — markdown.
6. **rules** — numbered list.
7. **examples (n)** — collapsible cards, expand to see in/out
   `FieldTree`s side-by-side (already done; just trim padding).
8. **config** — `FieldTree`, default depth 1.
9. **hooks** — same as today.

Use `MarkdownView` for `role` and `task` to render bold/italic if
present.

### Step 4 — Tab Events as log

Replace the bullet-card list with the existing `EventRow` virtualized
component (defined for the universal events tab,
`apps/frontend/src/components/agent-view/page-shell/event-row.tsx`).
Filter to events for this `agent_path`. Each row: timestamp ·
kind · summary, all on one 22px line. No bubbles, no nested cards.

If the event count exceeds 200, show a `Tail 200` chip allowing the
user to load more.

## Design alternatives

1. **Drop the Langfuse tab vs keep but slim.** Recommendation: drop —
   it's a single link.
2. **Tab Events: reuse `EventRow` vs new component.** Recommendation:
   reuse — the styling already matches and we get virtualization for
   free.
3. **Add a `ParametersTab` to the inspector now (composite leaves
   only) vs defer to Sequence 3.** Recommendation: defer. Drawer is
   the user's chosen UX (§9), not yet another inspector tab.

## Acceptance criteria

- [ ] `tab-experiment.tsx` and `tab-agent-langfuse.tsx` are deleted.
- [ ] `EDGE_TABS` has exactly four entries: Overview, Invocations,
  Prompts, Events.
- [ ] Tab Overview renders identity / input / output / role / task /
  rules / examples / config in vertical sections with labels on top.
- [ ] When `meta.langfuse_search_url` is present, the inspector header
  shows an inline `langfuse →` chip.
- [ ] Tab Events renders as a virtualized log; no bullet-card layout.
- [ ] `useUIStore` has no remaining references to `experiment` or
  `langfuse` tabs.
- [ ] `pnpm test --run` passes; tests referencing the deleted tabs
  are updated or removed.

## Test plan

- `inspector-shell.test.tsx` (create or update): assert four tabs
  visible; assert clicking a node renders the new vertical Overview;
  assert no `tab-experiment` / `tab-agent-langfuse` imports.
- `tab-agent-overview.test.tsx` (create): render with a fixture meta
  and assert vertical structure (`Eyebrow` + content per section).
- `tab-agent-events.test.tsx` (create or update): render with 50
  events; assert virtualization (limited number of rendered rows).

## Out of scope

- The graph layout itself (`agent-flow-graph.tsx`); the user's
  "parents can't be expanded" complaint is actually addressed by the
  existing chevron — we just need to make it more discoverable. That
  goes in a stretch goal here, not a blocker.

## Stretch goals

- Make the composite chevron larger and color-tinted so users see
  expand affordance immediately. Update `composite-flow-node.tsx`.
- Add a toolbar "Expand all composites" button that's currently
  buried (already in `agent-flow-graph.tsx:255-260`); promote it to
  the canvas chrome with a label, not just an icon.
- Inspector remembers its width; user can drag to resize (uses
  `SplitPane` already; just persist the ratio).
- When a leaf is selected and has parameters, surface a "trainable
  parameters (N)" eyebrow in the Overview tab linking to the Training
  tab with `?param=...` set.
