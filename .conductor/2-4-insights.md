# 2-4 Insights row: fingerprint, drift, sparklines, badges

## Scope

Build the row that sits between the metadata header (2-1) and the
interactive graph (2-2). This is the dashboard's "at-a-glance
intelligence" surface — the row that should make a senior engineer
stop and read it for ten seconds before doing anything else.

### You own

- `apps/frontend/src/components/agent-view/insights/`
  - `agent-insights-row.tsx` — composite container.
  - `fingerprint-card.tsx` — 7-hash reproducibility card.
  - `drift-strip.tsx` — horizontal hash_prompt timeline.
  - `cost-latency-sparklines.tsx` — three sparklines (cost,
    latency, tokens).
  - `backend-badges.tsx` — backend / model / sampling / renderer.
  - `value-distribution.tsx` — per-attribute mini-distribution
    (used by the IO popup *and* this row's "input shape" panel).
  - `registry.tsx` + `index.ts`.

### Depends on (iter-1 contracts)

- `GET /runs/{id}/summary` (existing).
- `GET /runs/{id}/invocations` (1-3).
- `GET /runs/{id}/agent/{path}/meta` (1-3) — for the configuration
  surface.
- `useUIStore.openDrawer` (1-1) — clicking a transition in the
  drift strip opens the prompt-diff drawer.

### Out of scope

- The header (2-1) and graph (2-2). Reference your composite
  component in 2-1's layout.
- Drawer content (3-x).

---

## Vision

The brief in `0-0-overview.md` calls this the "insights row" — but
that undersells it. This row is where operad's reproducibility
fingerprint and prompt-drift mechanics finally become *visible to
the user*. Done well, it's the first thing your data scientists
will screenshot.

Think:

- A user pulls up an Agent run and sees seven hashes in the
  fingerprint card — model / prompt / graph / input / output_schema
  / config / content. They click `hash_prompt` and copy it. Or
  click an icon next to it: "find all runs with this fingerprint".
- A 12px-tall horizontal strip below the fingerprint card shows
  every invocation as a tick, color-banded by `hash_prompt`. The
  user spots a transition where the color changes — they click it,
  and the prompt-diff drawer opens at that exact transition.
- Three tiny sparklines next to each other: cost over time,
  latency over time, tokens over time. Hover for per-call detail.
- A horizontal pill row of badges: backend, model, temperature,
  top_p, structured_io, renderer.
- A "value-shape" panel showing the distribution of recent input
  values for each attribute (categorical: top-N counts;
  numeric: mini-histogram).

This row is non-interactive at the layout level — it's a
read-only summary — but every element opens a relevant deeper
view when clicked.

---

## Components

### `FingerprintCard`

A small card. Header: "fingerprint". Body: seven rows, each:

```
hash_model         f1f2f3f4    [copy] [find runs]
hash_prompt        9a9b9c9d    [copy] [find runs]
...
```

The hash chip is the same `HashChip` from 2-1 (deterministic
color from hash). Use one of these for the title chip too.

`[find runs]` is a future feature — for v1, render the icon and
make it open `openDrawer({kind: "find-runs", payload: {hash:
"hash_prompt", value: "9a9b9c9d"}})`. The drawer view doesn't
exist yet; that's fine, it'll fall through to the stub. Mark
this as a "soon" capability with a small "(soon)" tooltip.

### `DriftStrip`

A 16px-tall SVG bar that spans the available width. Each
invocation is a tick whose width is proportional to the
invocation count (or fixed if there are <50 invocations). Color
each tick by `hash_prompt`. Render vertical color-change markers
between adjacent ticks where the hash flipped.

Interactions:

- Hover a tick → tooltip with invocation index, started_at, hash.
- Click a marker → `openDrawer({kind: "prompts", payload:
  {agentPath: rootPath, focus: invocationId}})` so the prompt-diff
  view (3-2) lands on that transition.

Below the strip, a small caption: "n invocations · k unique
prompts · last drift T ago".

### `CostLatencySparklines`

Three small inline sparklines (~120×24 px) using a tiny chart
library or hand-rolled SVG (recharts is overkill for this scale).
Each sparkline:

- Cost (USD per call) — green-leaning gradient.
- Latency (ms) — orange-leaning.
- Tokens (prompt+completion) — blue-leaning.

Hover any sparkline → tooltip with per-invocation values.
X-axis is invocation index, not time.

Below: totals, e.g. `total cost: $0.43 · avg 1.4s · 12k tokens`.

### `BackendBadges`

Pill row:

```
[ openai ]  [ gpt-4o-mini ]  [ T 0.7 ]  [ top_p 1.0 ]  [ structured ]  [ xml ]
```

If the agent has `default_sampling` overrides, show them with a
small "*" hint. If `Configuration.runtime.extra` has anything
non-empty, show a "+N" pill that opens the configuration view in
the agent edge popup.

### `ValueDistribution`

Reusable mini visualization for one attribute. Two modes:

- **Numeric** — sparkline / box plot of values over invocations.
- **Categorical** — top-5 bars with counts.

This component is *also* used by 3-3 (value-timeline drawer view)
and by 2-2 (IO popup). Build it once here and export from
`insights/index.ts`.

The insights row uses one `<ValueDistribution>` per top-level
input field (cap at e.g. 4 fields; show "+3 more" if there are
more). Empty state when there are no recent invocations.

### `AgentInsightsRow` (composite)

Lays out the four cards in a responsive grid:

```
┌────────────────────┬──────────────────────────────┐
│ FingerprintCard    │ DriftStrip                   │
├────────────────────┼──────────────────────────────┤
│ BackendBadges      │ CostLatencySparklines        │
└────────────────────┴──────────────────────────────┘
ValueDistribution × N (full-width)
```

On narrower screens, stack vertically.

---

## Implementation pointers

- The row should be entirely client-side computed from the
  invocations array — no new backend endpoints needed (1-3 covers
  the data sources).
- Hash → color: same helper as 2-1's `HashChip`. Export it from
  a shared `lib/hash-color.ts` so 2-1 and 2-4 don't duplicate.
- Distribution: `d3-array` has `bin` and `quantile`; if you don't
  want d3, hand-roll. Stay light.
- For the drift strip, render to SVG; canvas would be overkill.
  Throttle re-renders if the invocation count is huge — for >500
  invocations, downsample to a fixed bucket count.

---

## Polish targets

- The fingerprint card should make `hash_content` visually
  distinct from `hash_prompt` (e.g. a subtle "this hash captures
  the agent" tooltip). Users will care about which hash to share.
- Drift strip needs to feel like a *strip*, not a chart. Don't
  give it axes; let the color do the talking.
- Sparklines: enforce minimum-2-points-or-empty-state so single-
  call agents don't get a degenerate flat line.
- Backend badges: when the model is local (e.g. llamacpp), show
  a small "local" indicator next to the backend pill.
- ValueDistribution should degrade gracefully on string fields
  with high cardinality — switch to "see all values" link that
  opens 3-3's drawer.

---

## Be creative

- Add anything that exploits operad's surface and is cheap to
  compute. Examples to consider:
  - **Cassette indicator** if the run was replayed (read from
    `summary.cassette_mode` if it exists; otherwise from event
    metadata).
  - **Live trail** — a subtle pulse on the drift strip when a
    new invocation lands.
  - **Best-of comparison** — if multiple invocations share the
    same `hash_prompt` and same `hash_input`, hover one to see
    the others stacked.
- The row is the dashboard's first impression. Push it.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open a non-algorithm run with multiple invocations. Confirm:
# - Fingerprint card shows all 7 hashes; copy buttons work.
# - Drift strip shows colored ticks; clicking a transition opens
#   the prompts drawer (stub for now).
# - Sparklines render and tooltip on hover.
# - Backend badges reflect the agent's config.
# - Value distributions render for each top-level input attribute.
```
