# 06-02 Langfuse links everywhere a span exists

**Branch**: `dashboard/langfuse-everywhere`
**Wave**: Sequence 6, parallel batch
**Dependencies**: none (uses existing `langfuseUrlFor` helper)
**Estimated scope**: small

## Goal

Surface a `langfuse →` deep-link wherever the dashboard knows about a
specific span: per-row in algorithm Invocations tables, per-step in
parameter evolution timelines, per-event in the events log (already
done), per-invocation in the inspector, per-cell in Sweep, per-round
in Debate, etc.

## Why this exists

§13 of the inventory: `OtelObserver` ships every span to Langfuse.
The dashboard already knows the URL pattern (`langfuseUrlFor`); we
just don't surface it consistently.

## Files to touch

- `apps/frontend/src/lib/langfuse.ts` — add a helper
  `langfuseLinkProps(url, runId, spanId)` that returns
  `{ href, target, rel, title }` to standardize chip rendering.
- All algorithm tab components (Sequence 5 outputs) — append a
  langfuse column or per-row link where applicable.
- `apps/frontend/src/components/agent-view/parameter-evolution/text-evolution.tsx`,
  `float-evolution.tsx`, etc. — add a `langfuse →` chip per
  selected step (already partially required in brief `03-05`'s
  WhyPane, but this brief covers the timeline-row-level chips).
- `apps/frontend/src/components/agent-view/graph/inspector/inspector-shell.tsx` —
  surfaces it via a chip next to the title (already required by
  `02-03`; keep one canonical implementation).

## Contract reference

`00-contracts.md` §13 (palette + invariant: chips never call mutating
endpoints; they navigate to Langfuse only).

## Implementation steps

### Step 1 — `langfuseLinkProps` helper

```ts
export function langfuseLinkProps(
  base: string | null | undefined,
  runId: string,
  spanId?: string | null,
): { href: string; target: "_blank"; rel: "noopener noreferrer"; title: string } | null {
  if (!base) return null;
  const href = spanId
    ? `${base.replace(/\/$/, "")}/trace/${runId}#${spanId}`
    : `${base.replace(/\/$/, "")}/trace/${runId}`;
  return {
    href,
    target: "_blank",
    rel: "noopener noreferrer",
    title: spanId ? `Open span ${spanId.slice(0, 8)} in Langfuse` : "Open trace in Langfuse",
  };
}
```

### Step 2 — Component audit checklist

- [ ] `inspector-shell.tsx` (chip in header).
- [ ] `parameter-drawer.tsx` (chip in header per selected step's
  invocation; reuse via `WhyPane`).
- [ ] Each `*-evolution.tsx` (chip per step, when
  `point.langfuseUrl` is set).
- [ ] Each algorithm `Invocations` column descriptor (brief `05-11`)
  has a `langfuse` column with `kind:"link"`.
- [ ] `tab-agent-events.tsx` (already wired; verify).

### Step 3 — Manifest dependency

When `manifest.langfuseUrl` is null, all chips are hidden. Render no
placeholder. The dashboard must not show broken affordances.

## Acceptance criteria

- [ ] Every place that has a span ID surfaces a langfuse link when
  the manifest has a base URL.
- [ ] When the manifest URL is null, no langfuse chips are rendered
  anywhere.
- [ ] All chips open in a new tab with `noopener noreferrer`.
- [ ] `pnpm test --run` passes.

## Test plan

- `lib/langfuse.test.ts`: extend with `langfuseLinkProps` cases
  (null base, with span, without span).
- Visual: with `LANGFUSE_HOST` set in `.env`, chips appear; without,
  they're absent.

## Stretch goals

- A "copy span URL" affordance on hover (small clipboard icon next
  to each chip).
- A keyboard shortcut `g l` opens the active span in Langfuse.
