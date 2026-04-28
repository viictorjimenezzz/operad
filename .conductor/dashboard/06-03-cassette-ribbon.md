# 06-03 Cassette and trace status ribbon

**Branch**: `dashboard/cassette-ribbon`
**Wave**: Sequence 6, parallel batch
**Dependencies**: `01-01` (manifest cassette fields)
**Estimated scope**: small

## Goal

Add a slim ribbon under the topbar showing operad's
record/replay/trace state. The ribbon makes the user aware that the
runs they're viewing might come from a cassette (replay), or that
new runs are being recorded to a JSONL trace.

## Why this exists

- §17 of the inventory exposes cassettes as the offline replay
  story. Without UI surfacing, users mistakenly assume "live" data.
- The user explicitly said: "Keep [the ribbon]" in the design
  decisions, even though the dashboard is monitor-only.

## Files to touch

- New: `apps/frontend/src/components/panels/cassette-ribbon.tsx`.
- `apps/frontend/src/dashboard/Shell.tsx` — render the ribbon under
  `GlobalStatsBar`.
- `apps/frontend/src/components/panels/cassette-ribbon.test.tsx` —
  test.

## Contract reference

`00-contracts.md` §15 (data emission), §10 (manifest cassette
fields).

## Implementation steps

### Step 1 — Component

```tsx
export function CassetteRibbon() {
  const m = useManifest();
  if (m.isLoading || !m.data) return null;
  const showCassette = m.data.cassetteMode != null;
  const showTrace = !!m.data.tracePath;
  if (!showCassette && !showTrace) return null;
  return (
    <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-3 py-1 text-[11px]">
      {showCassette ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[--color-warn]" />
          cassette: {m.data.cassetteMode}
          {m.data.cassettePath ? <code className="font-mono text-muted-2">{m.data.cassettePath}</code> : null}
          {m.data.cassetteStale ? <Pill tone="error" size="sm">stale</Pill> : null}
        </span>
      ) : null}
      {showTrace ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[--color-accent]" />
          trace: {m.data.tracePath}
        </span>
      ) : null}
    </div>
  );
}
```

### Step 2 — Render in Shell

```tsx
<GlobalStatsBar subtitle="dashboard" />
<CassetteRibbon />
<div className="flex flex-1 overflow-hidden"> ... </div>
```

The ribbon does NOT render when both fields are absent (the common
case for live, non-cassette dashboards).

## Design alternatives

1. **Ribbon vs status pill in the topbar.** Recommendation: ribbon —
   the user explicitly said "keep it" and visibility matters for
   semantics.
2. **Show even when fields are absent (so the user learns the
   feature exists).** Recommendation: hide. Empty UI affordances
   train users to ignore them.

## Acceptance criteria

- [ ] When `cassetteMode` is set, the ribbon shows it with the path
  and stale indicator.
- [ ] When `tracePath` is set, the ribbon shows it.
- [ ] When neither, the ribbon does not render.
- [ ] `pnpm test --run` passes.

## Test plan

- `cassette-ribbon.test.tsx`: render with all four combinations
  (cassette only, trace only, both, neither).
- Manual: set `OPERAD_CASSETTE_PATH=/tmp/foo`, restart dashboard,
  see ribbon.

## Stretch goals

- Tooltip on the cassette pill explaining what cassette mode does
  (links to docs).
- A "refresh cassette check" button that re-evaluates `cassetteStale`
  on demand (calls a new endpoint or just refetches manifest).
- Per-run badge: in the algorithm breadcrumb, when the run was
  produced under cassette mode, show a small "cassette" chip.
