# 3-5 — Langfuse summary card + per-event deep links

> **Iteration**: 3 of 4. **Parallel slot**: 5.
> **Owns**: a NEW shared panel for Langfuse summary, a small per-event
> link helper, and integration into existing run-detail layouts where
> it doesn't conflict with iter-3 algorithm work.
> **Forbidden**: any chart component, layout-specific work owned by
> 3-1/3-2/3-3/3-4.

## Problem

The strategic split is "agent traces in Langfuse, everything else in
the dashboard." Today the dashboard:

- **Duplicates** Langfuse: tokens and cost tiles in the run header
  (always $0.00 for offline demos — visually dead).
- **Promises but doesn't deliver** Langfuse deep-links: the README
  says clicking a run goes to `{LANGFUSE_PUBLIC_URL}/trace/{run_id}`,
  but no such link exists in the UI today.
- **Hides** Langfuse: the per-event Langfuse span link is buried,
  making the integration feel optional rather than load-bearing.

## Scope

### Owned files

- New: `apps/frontend/src/shared/panels/langfuse-summary-card.tsx` —
  a card showing total spans, total tokens, total cost, last error,
  with a click-through to the Langfuse trace.
- `apps/frontend/src/shared/panels/langfuse-link.tsx` (currently a
  355-byte stub per the explore report) — replace with a real
  link-out component.
- New: `apps/frontend/src/lib/langfuse.ts` — small helper that builds
  the Langfuse URL from `manifest.langfuseUrl` + `runId` (or
  `runId + spanId` for per-event).
- New: `apps/frontend/src/shared/panels/langfuse-summary-card.test.tsx`
  and `langfuse-link.test.tsx`.
- `apps/frontend/src/layouts/default.json` — wire the
  `<LangfuseSummaryCard />` into the default layout's overview.

### Forbidden files

- Other layouts (3-1, 3-2, 3-3, 3-4 own those — they will *consume*
  your component).
- Chart components.
- Backend code (the manifest endpoint already exists from 1-2).

## Direction

### Where Langfuse data comes from

The `<LangfuseSummaryCard />` does NOT call Langfuse APIs from the
browser. Instead:

- The dashboard already collects token/cost in `runs.py` (this exists
  today; verify after 1-2 lands).
- The card presents that summary + a link out.
- The link uses `manifest.langfuseUrl + '/trace/' + runId` (validated
  by checking `/api/manifest` → `langfuseUrl` is non-null).

If `langfuseUrl` is null (no Langfuse configured), the card shows the
local summary only and hides the link button. Don't make Langfuse a
hard dependency.

### Card shape

```
┌─────────────────────────────────┐
│ LANGFUSE                  ↗     │
│  spans:    127                  │
│  tokens:   prompt 2,438 + ...   │
│  cost:     $0.0042              │
│  errors:   0                    │
│  last:     "openai-1.5s ago"    │
│  [view in Langfuse →]           │
└─────────────────────────────────┘
```

If Langfuse is not configured: no header arrow, no view button, just
the summary fields.

### Per-event link helper

In the events table (already rendered per run), add a small "↗"
icon button per row that links to
`{langfuseUrl}/trace/{runId}?observation={spanId}` — the span id
should be in the event metadata. Verify the metadata field; if it's
not there, document the gap and add a TODO. Don't fail noisily.

### Layout integration

- `default.json`: add the summary card to the overview tab. (You
  own this file.)
- Other layouts (`evogradient.json`, `trainer.json`, etc.) will be
  modified by their respective iter-3 owners to include the card.
  **Coordinate** — but since each owner already controls their layout
  JSON, this is just documentation.

To make this easy: provide a single component that takes a `runId`
prop and renders correctly with no other config. iter-3 owners drop
`{ "type": "langfuse-summary-card", "props": { "runId": "$run.id" }}`
into their layout's `tree`.

### Drop dashboard token/cost duplicates

This is bigger than 3-5 alone — touches the run-detail header, the
overview tab on every layout. **Out of scope** for this task; instead,
file a follow-up task or note that iter-4 polish will remove them.
Today the headers are rendered by individual layout JSONs; iter-3
owners can choose to drop them when they update their layout.

What 3-5 does: provide the *better* alternative (the summary card)
and use it in `default.json`. Other agents adopt it.

## Acceptance criteria

1. The `<LangfuseSummaryCard />` renders correctly with:
   - Langfuse configured: shows summary + link button.
   - Langfuse not configured: shows summary only, no broken link.
2. Click "view in Langfuse" opens
   `{langfuseUrl}/trace/{runId}` in a new tab.
3. The default layout (for unknown algorithms) shows the card.
4. Per-event ↗ link works for events with `spanId` metadata; gracefully
   absent for events without.
5. Tests cover both Langfuse-configured and unconfigured states.

## Dependencies & contracts

### Depends on

- 1-2: `/api/manifest` returns `langfuseUrl`.
- 2-2: layout auto-discovery so the card can be referenced by JSON.

### Exposes

- `<LangfuseSummaryCard runId={…} />` for use in any layout.
- `langfuseUrlFor(runId, spanId?)` helper from `lib/langfuse.ts`.

## Direction notes / SOTA hints

- The Langfuse OTel observer aligns `trace_id == run_id`, so URLs
  resolve directly without any mapping table. Verify this against the
  `OtelObserver` source if you want to be sure.
- `manifest.langfuseUrl` should NEVER end with a trailing slash; the
  helper should normalize to avoid `//trace/` URLs.
- For the "↗" external-link icon: lucide-react's `ExternalLink`.

## Risks / non-goals

- Don't query Langfuse APIs from the browser (auth complexity).
- Don't add a "compare span counts across runs" feature — that's
  iter-4-1.
- Don't render any LLM call content client-side; that's Langfuse's
  job.

## Verification checklist

- [ ] With Langfuse running locally, the card renders + link works.
- [ ] With Langfuse turned off (or `langfuseUrl=null`), the card
      degrades cleanly.
- [ ] Tests pass.
- [ ] Default layout shows the card on the overview tab.
