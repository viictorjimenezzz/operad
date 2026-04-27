# 01 — Critical-path primitives

**Stage:** 1 (serial; blocks everything in Stage 3)
**Branch:** `dashboard-redesign/01-primitives`
**Worktree:** required (single agent, no parallel siblings)

## Goal

Land the small set of cross-cutting primitives that every other brief
consumes: the curated color palette, the `RunTable` primitive, the
bug-fixed `MultiSeriesChart`, the new `CollapsibleSection`, the new
`MarkdownView`/`MarkdownEditor`, and a few bug fixes that the rest of
the redesign depends on. This is not creative work — it is plumbing.
But the rest of the redesign cannot start cleanly until this is in.

## Read first

- `00-CONTRACTS.md` §1 (JSON layout shape), §2 (component props),
§3 (color palette), §8 (forbidden patterns).
- `INVENTORY.md` §1 (Agent primitive — what `hash_content` is and why
it's the right identity color seed), §13 (observers — `langfuse_url`
surfaces), §20 (reproducibility hashes — what each hash means in a
table swatch).
- `apps/frontend/src/components/ui/multi-series-chart.tsx` — the bug.
- `apps/frontend/src/components/agent-view/overview/invocations-banner.tsx:67-74`
— the "Latest invocation" eyebrow.
- `apps/frontend/src/components/agent-view/graph/agent-flow-graph.tsx:314-321`
— the empty-state branch we want to fix for single-leaf agents.
- `apps/frontend/src/styles/tokens.css` — token base.

## Files to touch

Create:

- `apps/frontend/src/components/ui/run-table.tsx`
- `apps/frontend/src/components/ui/collapsible-section.tsx`
- `apps/frontend/src/components/ui/markdown.tsx` (exports
`MarkdownView`, `MarkdownEditor`)
- `apps/frontend/src/hooks/use-url-state.ts` (the canonical URL state
helper, per `00-CONTRACTS.md` §6)
- Tests:
  - `apps/frontend/src/components/ui/run-table.test.tsx`
  - `apps/frontend/src/components/ui/collapsible-section.test.tsx`
  - `apps/frontend/src/components/ui/markdown.test.tsx`
  - `apps/frontend/src/lib/hash-color.test.ts` (new — verify palette
  rounding stability)

Edit:

- `apps/frontend/src/styles/tokens.css` — add `--qual-1..12` per
`00-CONTRACTS.md` §3.1.
- `apps/frontend/src/lib/hash-color.ts` — round to palette per §3.2.
- `apps/frontend/src/components/ui/multi-series-chart.tsx` — single-
point series fix.
- `apps/frontend/src/components/ui/index.ts` — re-export new primitives.
- `apps/frontend/src/components/ui/registry.tsx` — register
`CollapsibleSection`, `MarkdownView`, `MarkdownEditor`, `RunTable` for
the JSON renderer.
- `apps/frontend/src/components/agent-view/graph/agent-flow-graph.tsx`
— single-leaf empty-state fix (lines 314-321 region).
- `apps/frontend/src/components/agent-view/overview/invocations-banner.tsx`
— delete the `SingleInvocation` branch (replaced by the new
single-invocation Overview in Brief 03; keep `MultiSummary` and
`Empty` for now).

Delete:

- nothing yet — Brief 02 deletes legacy routes/tabs; Brief 04 deletes
the inline tables. This brief only adds primitives + fixes.

## API contracts (from 00-CONTRACTS.md)

You implement to the props shapes in `00-CONTRACTS.md` §2.1, §2.2, §2.3,
§2.4. Those are the contract. Do not invent additional props without
adding them to the contracts doc first.

## Specific work items

### 1. Curated palette + `hashColor` rewrite

`tokens.css`: append the `--qual-1..12` block from `00-CONTRACTS.md`
§3.1 verbatim.

`hash-color.ts`: rewrite to round into the palette.

```ts
const PALETTE_SIZE = 12;
export function hashColor(identity: string | null | undefined): string {
  if (!identity) return "var(--qual-7)";          // accent default
  let h = 0;
  for (let i = 0; i < identity.length; i++) h = (h * 31 + identity.charCodeAt(i)) | 0;
  const idx = ((h % PALETTE_SIZE) + PALETTE_SIZE) % PALETTE_SIZE;
  return `var(--qual-${idx + 1})`;
}
```

The function returns CSS strings (not hex). Test that it is
deterministic and stable: same identity always returns same value;
identities that are 1 character apart land on different palette slots
when possible (the Modulo-12 collision rate is fine for ≤200 active
identities).

### 2. `RunTable` primitive

Implementation reference: see `00-CONTRACTS.md` §2.1 for the full prop
shape.

Layout shape (compact density default):

```
┌────┬──────────────────────────────────────────────────────────┐
│    │  ●● State  Run                Started  Latency  Tokens  │
├────┴──────────────────────────────────────────────────────────┤
│ ▒▒ │  ●  ok    62af09c…           14m ago   1.4s     510     │
│ ▒▒ │  ●  err   4b57d24…            9m ago   3.9s     312     │
│ ▒▒ │  ●  live  9cdd193…           live      —        —       │
│ ▒▒ │  ●  ok    967f06b…           7s ago    1.2s     444     │
└────┴──────────────────────────────────────────────────────────┘
[ < 1-50 of 222 > ]    Columns ▾
```

Required:

- 4-px left rail = `hashColor(row.identity)`. When the row is the
active one (route matches `rowHref(row)`), bump to 6-px and
outline.
- Header is sticky on scroll inside the table's container.
- Sort indicator (▲/▼) shown on the active sort column.
- Click anywhere on the row navigates to `rowHref(row)`. `cmd`/`ctrl`-
click opens in new tab. `shift`-click toggles selection (when
`selectable`).
- "Columns" menu is a `Popover` from `radix-ui` (already a dep — verify
via `pnpm why @radix-ui/react-popover`).
- Sparkline column renders inline at 60×16px; the gradient stays
visible because the row height is 28px.
- Pager footer renders only when total rows > pageSize.
- `groupBy` produces collapsible group headers with row count.
- URL state: `?sort=`, `?cols=` per §6.
- Keyboard nav: `j` / `k` (or `↓` / `↑`) move highlight; `Enter` or `o`
navigates; `space` toggles selection. Highlight persists in
component state, not URL.

Do **not** include comparison-anchor logic; Brief 04 wires multi-select
into the existing `useUIStore.setComparisonInvocation` — `RunTable` only
exposes `onSelectionChange`.

### 3. `MultiSeriesChart` single-point fix

Current bug (`apps/frontend/src/components/ui/multi-series-chart.tsx`
lines 213-235): when a series has 1 point, the path string is `M x y`
with no `L`. SVG renders this as nothing.

Fix: when `pts.length === 1`, render a circle marker at the point
instead of a path. Keep path rendering for ≥2 points.

```tsx
{pts.length === 1 ? (
  <circle cx={xToPx(pts[0].x).toFixed(2)} cy={yToPx(pts[0].y).toFixed(2)}
          r={2.5} fill={color} opacity={0.92} />
) : (
  <path d={pathStr} … />
)}
```

This unblocks two consumers immediately (group page latency chart,
group cost scatter) but the *real* fix for those is to pass a
multi-point series — Brief 04 does that. Both fixes are required:
the chart should not silently swallow one-point series.

### 4. `AgentFlowGraph` single-leaf fallback

`agent-flow-graph.tsx` lines 314-321: when `nodes.length === 0` the
empty state is correct. When `nodes.length === 1 && edges.length === 0`
(a single-leaf agent like the Reasoner in examples 03/04), render the
single node prominently using the existing `AgentNodeCard`. The current
behavior is to render an empty graph (no nodes, no edges, looks broken).

Concretely:

- If `agentGraph.nodes.length === 0` → existing "graph not ready"
empty state.
- If `agentGraph.nodes.length === 1 && agentGraph.edges.length === 0`
→ render that one node centered, with the inspector pane also showing
it as the only selectable node.

### 5. Delete `InvocationsBanner.SingleInvocation`

The eyebrow "Latest invocation" comes from
`apps/frontend/src/components/agent-view/overview/invocations-banner.tsx`
lines 63-115 (the `SingleInvocation` component). Delete that function
entirely. Update `InvocationsBanner` to:

```ts
export function InvocationsBanner(props: InvocationsBannerProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  const invocationsParsed = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.invocations,
  );
  if (!summaryParsed.success || !invocationsParsed.success) return <Skeleton />;
  const rows = invocationsParsed.data.invocations;
  if (rows.length === 0) return <Empty />;
  if (rows.length === 1) return null;     // single-invocation Overview owns this state (Brief 03)
  return <MultiSummary rows={rows} runId={props.runId ?? null} />;
}
```

Brief 03 then removes `InvocationsBanner` from
`apps/frontend/src/layouts/agent/overview.json` entirely; this brief
only neutralizes the wrong-text path.

### 6. `CollapsibleSection`

Per `00-CONTRACTS.md` §2.3. Implementation:

- Reuse `framer-motion` (already a dep) for height animation.
- Default-collapsed unless `defaultOpen` is true OR
`window.location.hash === "#section=" + id`.
- Header is a button (a11y) with `aria-expanded`.
- Preview slot sits next to a `ChevronDown` (180° on open) on the
header row.
- Body padding matches `PanelCard` flush body (`p-3`).

### 7. `MarkdownView` / `MarkdownEditor`

Per `00-CONTRACTS.md` §2.4. Implementation:

- Add `react-markdown@^9` and `remark-gfm@^4` as deps (verify with
`pnpm why` first).
- View renders Markdown read-only. Edit mode swaps to a `<textarea>`
with a tiny "Preview" toggle that switches the textarea into rendered
mode.
- Save calls `onSave(text)`; while pending, show inline spinner; on
error, render `--color-err` border + retry button.
- Strip raw HTML (`react-markdown` does this by default).

### 8. `useUrlState` hook

Per `00-CONTRACTS.md` §6. Centralizes reads/writes to the URL
querystring + hash so nothing ad-hocs around `useSearchParams`. Must
play well with `react-router-dom` `useSearchParams`. Provide:

```ts
function useUrlState<T extends string>(key: T): [string | null, (next: string | null) => void];
function useUrlList(key: string, sep = ","): [string[], (next: string[]) => void];
function useUrlHash(): [string, (next: string) => void];
```

## Design alternatives

### A1: Palette stability

- **(a)** 12 hues, hash modulo 12 (recommended; per `00-CONTRACTS.md`).
- **(b)** 8 hues. Lower collision visibility; but with 200+ active
identities the spread is thinner. **Reject.**
- **(c)** Per-rail palette. Agents get one slice, Algorithms another.
Makes the rails feel distinct but breaks the "same color = same
thing" promise across the dashboard. **Reject.**

### A2: `RunTable` virtualization

- **(a)** Plain DOM rows + pager (recommended). Simple, fast enough for
≤500 rows, and pager is needed anyway for sweeps.
- **(b)** `@tanstack/react-virtual`. Adds a dep; pays off only at
10k+ rows, which we don't have. **Reject for now.**

### A3: `MultiSeriesChart` 1-point handling

- **(a)** Render a circle marker (recommended).
- **(b)** Drop the series silently (current behavior). **Reject — it's
the bug.**
- **(c)** Auto-extrapolate to a horizontal line. **Reject — invents
data.**

## Acceptance criteria

- `tokens.css` defines `--qual-1..12` and they render in DevTools.
- `hashColor(x)` returns one of `var(--qual-1..12)` for any
non-empty `x`. Stable across calls.
- `MultiSeriesChart` renders a visible circle for a single-point
series. Existing 2+ point series still draw lines (snapshot test).
- `RunTable` renders 50 rows of fake data with all features
(sort, color rail, sparkline column, columns menu, pager, multi-
select, keyboard nav). Stories or test fixtures included.
- `CollapsibleSection` honors `#section=<id>` URL hash to open by
default; toggles persist for the session (component state only —
no localStorage).
- `MarkdownView` renders headings, lists, code blocks, links;
`MarkdownEditor` saves via injected callback and shows pending
state.
- `useUrlState` round-trips the conventions in `00-CONTRACTS.md`
§6: `?sort=`, `?cols=`, `?compare=`, `#section=`.
- `AgentFlowGraph` renders the single-leaf case as a centered
node (manual smoke against examples 03/04 once the dashboard rebuild
picks up).
- `InvocationsBanner` returns `null` when `rows.length === 1`.
- `pnpm test --run` green.
- `make build-frontend` succeeds.

## Test plan

- **Unit:** `run-table.test.tsx` covers sort, multi-select, columns
menu, keyboard nav, group headers, pager. `hash-color.test.ts`
asserts determinism and palette membership. `multi-series-chart`
snapshot for 1-point + 2+-point. `markdown.test.tsx` covers save
flow + preview toggle.
- **Visual:** add fixture data + a Storybook-ish standalone page
(`apps/frontend/src/dashboard/pages/__dev/PrimitivesGallery.tsx`,
route `/__dev/primitives`, only mounted when `import.meta.env.DEV`).
- **Contract:** `tokens.css` has all 12 vars; `hashColor` returns
exactly the contracted format.

## Out of scope

- Drag/resize panels (forbidden in `00-CONTRACTS.md` §8).
- Compare drawer (Q3 says skip).
- Saved-view "auto-save" badge (deferred per `proposal.md` §9).
- Edits to per-rail layouts (Briefs 02, 04 own those).
- Backend changes (Brief 14 owns those).

## Hand-off

When you're done, post the PR with:

1. The acceptance-criteria checklist above, each marked off with
  file:line evidence.
2. Screenshot of `/__dev/primitives` showing every primitive.
3. A note on `pnpm why react-markdown` and `pnpm why @radix-ui/react-popover`
  results (whether you added or reused).
4. Any contract additions you needed (post in PR description; the
  parent agent updates `00-CONTRACTS.md`).

