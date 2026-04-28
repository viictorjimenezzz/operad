# 06-04 Compare mode

**Branch**: `dashboard/compare-mode`
**Wave**: Sequence 6, parallel batch
**Dependencies**: `01-02` (HashRow), `05-11` (Invocations multi-select)
**Estimated scope**: medium

## Goal

Promote the existing `/experiments` route into a real Compare page.
Anywhere the user can multi-select rows (Invocations tabs, Sweep
cells, Beam candidates), provide a sticky "Compare N" CTA that
navigates to the page with the selected runs preloaded.

The page renders side-by-side panels for I/O, hash diff, parameter
diff, latency / cost / score deltas, plus per-side Langfuse links.

## Why this exists

- §19 of the inventory exposes typed in-place mutations
  (`AppendRule`, `EditTask`, `SetRole`) that are the
  fingerprints of an optimization step. Compare mode is where these
  ops light up.
- §20: hash diffs are operad's "what changed" signal; comparing two
  runs shows them simultaneously.

## Files to touch

- `apps/frontend/src/dashboard/pages/ExperimentsPage.tsx` — rewrite
  body to be a compare canvas; keep the existing route.
- New:
  `apps/frontend/src/components/agent-view/compare/` — components
  per panel.
- `apps/frontend/src/dashboard/pages/AgentGroupRunsTab.tsx` — wire
  the existing "Compare" button to the Compare page (already there,
  verify destination URL).
- All algorithm Invocations tab descriptors (brief `05-11`) — make
  multi-select default-on; CTA appears when ≥ 2 selected.

## Contract reference

`00-contracts.md` §6 (HashRow), §13 (folders).

## Implementation steps

### Step 1 — URL contract

```
/experiments?runs=run_id_a,run_id_b,run_id_c
```

Up to 4 runs; the page renders 2-4 columns. > 4 → show a chip
"select fewer to compare side by side" and only render the first 4.

### Step 2 — Page layout

Header: a chip per run (color-coded by `hash_content`) with a small
"x" to remove it from the comparison.

Body: vertical sections, each rendering N columns:

1. **Identity strip** — class · agent path · `HashRow`.
2. **Hash diff matrix** — 7 rows × N columns; each cell is the
   hash monogram, cells where the hash differs from a reference (col
   1) are highlighted.
3. **Parameter diff** — for each trainable parameter, show its
   per-run value using the appropriate per-type evolution view
   (single-step rendering — reuse briefs `03-03`, `03-04`).
4. **Op log** — when `metadata.ops` is present (typed mutations
   §19), render them as a colored op log per run. Format:
   `+ AppendRule(path="reasoner", rule="Be concise.")` or
   `~ EditTask(path="...", from=..., to=...)`.
5. **Outcomes** — latency, cost, tokens, terminal score deltas.
6. **Per-run Langfuse links**.

### Step 3 — Per-cell color

Each column has a 4px-tall colored bar at the top using
`hashColor(run.hash_content)`. A column header chip shows the run
id and class.

### Step 4 — Multi-select hooks

The brief `05-11` `InvocationsTab` already supports multi-select
(via `RunTable.selectable`). Add a sticky-bottom CTA that appears
when `selected.length >= 2`:

```tsx
{selected.length >= 2 ? (
  <StickyBar>
    <span>{selected.length} selected</span>
    <Button onClick={() => navigate(`/experiments?runs=${selected.join(",")}`)}>
      Compare
    </Button>
  </StickyBar>
) : null}
```

`AgentGroupRunsTab.tsx` already has this; brief `05-11` adds it to
algorithm Invocations.

## Design alternatives

1. **Side-by-side columns vs stacked panels with diff highlights.**
   Recommendation: columns. Easier to scan; matches W&B compare.
2. **Limit at 2 vs up to 4 runs.** Recommendation: up to 4.
   Three-way comparison is common for "before / candidate / control"
   stories.

## Acceptance criteria

- [ ] `/experiments?runs=a,b` renders 2 columns; `?runs=a,b,c,d`
  renders 4.
- [ ] All 6 sections present for each compared run.
- [ ] Compare CTA appears on multi-select in Invocations tabs and
  Sweep Cells.
- [ ] `pnpm test --run` passes.

## Test plan

- `experiments-page.test.tsx`: render with 2-run fixture; assert
  hash diff matrix shows the right cells; assert op log renders
  when `metadata.ops` is present.

## Stretch goals

- A "highlights" mode that hides sections where every run is
  identical and bolds where they differ.
- Per-section collapse/expand.
- Export the comparison as a markdown report (clipboard-only;
  monitor-safe).
