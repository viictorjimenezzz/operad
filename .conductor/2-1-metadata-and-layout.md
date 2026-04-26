# 2-1 Agent metadata header + agents layout

## Scope

Build the **header** of the agent-detail page — the metadata panel
+ invocations table — and wire it into a new top-level layout
(`agents.json`) that renders for any non-algorithm run.

### You own

- `apps/frontend/src/components/agent-view/metadata/`
  - `agent-metadata-panel.tsx`
  - `invocations-table.tsx`
  - `script-origin-chip.tsx`
  - `hash-chip.tsx` (small reusable; copy-on-click)
  - `registry.tsx` + `index.ts`
- `apps/frontend/src/layouts/agents.json` (new top-level layout).
- `apps/frontend/src/layouts/index.ts` — extend the resolver so
  that runs with `algorithm_path == null` (or `"*"` fallback)
  resolve to `agents.json`. **Delete** any reference to the old
  `default.json` flow.

### Depends on (iter-1 contracts)

- `useUIStore.openDrawer(...)` for click-throughs (already
  delivered by 1-1).
- `GET /runs/{id}/invocations` (1-3).
- The new component-folder convention (1-1).

### Out of scope

- The interactive graph (2-2 owns).
- The drawer shell (2-3 owns; you can call `openDrawer` and trust
  it lands).
- The insights row — fingerprint, drift strip, sparklines — (2-4
  owns; reference its components by name in the layout).

---

## Vision

This is the first thing the user sees. It must answer the question
*"what is this Agent and what's it been doing?"* in three seconds.

Don't make it boring. The header should feel like a passport page
— compact but information-dense, every glyph earning its space.
Concretely:

- **Agent identity** at the top: class name, `hash_content`
  (clickable chip), the `script` that invoked it, optionally a
  human label if one is set.
- **Invocations table** below: one row per `invoke()` call,
  columns for timestamp, latency, tokens (prompt+completion),
  cost (if known), `hash_prompt` chip (color-coded by stable hash),
  status badge, and a "view in Langfuse" icon-link. Hover a row
  → preview of input/output. Click → opens IODetail in the drawer
  (drawer view doesn't exist yet but trust 2-3's stub).
- **Streaming feel**: while a run is live, new rows pulse in.

---

## Layout (`agents.json`)

```json
{
  "algorithm": "*",
  "version": 1,
  "dataSources": {
    "summary":     { "endpoint": "/runs/$context.runId/summary" },
    "invocations": { "endpoint": "/runs/$context.runId/invocations" },
    "io_graph":    { "endpoint": "/runs/$context.runId/io_graph" }
  },
  "spec": {
    "root": "page",
    "elements": {
      "page": {
        "type": "Col",
        "props": { "gap": 16 },
        "children": ["header", "insights", "graph", "drawer"]
      },
      "header": {
        "type": "AgentMetadataPanel",
        "props": { "summary": "$queries.summary", "invocations": "$queries.invocations" }
      },
      "insights":  { "type": "AgentInsightsRow",  "props": { "summary": "$queries.summary", "invocations": "$queries.invocations" } },
      "graph":     { "type": "InteractiveGraph",  "props": { "ioGraph": "$queries.io_graph", "runId": "$context.runId" } },
      "drawer":    { "type": "SideDrawer",        "props": { "runId": "$context.runId" } }
    }
  }
}
```

Refine to taste. The layout shape is a starting point, not
gospel — you can split the metadata panel into header + table at
the layout level if it lets you reuse pieces elsewhere, or pull
fields into `Tabs` if the page gets long. The **must-haves** are:
the header is at top, the graph fills the main area, the drawer
mounts on the right.

`AgentInsightsRow`, `InteractiveGraph`, and `SideDrawer` are
sibling-stream components — reference by name. They'll be there
when iter-2 merges as a batch.

---

## Components

### `AgentMetadataPanel`

Top card. Lays out:

- Class name (large, monospace), kind badge (leaf vs composite).
- Copyable `hash_content`.
- Script origin chip: file name (basename of `summary.script`) +
  hover tooltip showing full path.
- Run id chip + Langfuse deeplink (small icon).
- Run state badge (live / ended / error) — pulse animation on
  live.
- Started_at, duration, total token cost summary.

### `InvocationsTable`

Virtualized list (we expect tens-to-hundreds of rows on a long
run; React Window or TanStack Table). Columns:

| Column | Notes |
| --- | --- |
| `#` | Sequential index. |
| `started_at` | Relative ("3s ago") with absolute on hover. |
| `latency_ms` | Color-coded (green<1s, yellow<5s, red≥5s). |
| `prompt_tokens` / `completion_tokens` | One cell, e.g. `820 / 412`. |
| `hash_prompt` | Small chip; same hash → same color across rows (so the user can spot prompt drift at a glance). |
| `status` | OK / error icon. Hover error → tooltip with last_error. |
| Actions | Langfuse link · "view I/O" (opens drawer) · "diff vs prev" (opens drawer with prompt-diff for this row) |

### `HashChip`

Reusable: takes a hash string, shows the first 6 chars with a
deterministic background color (hash → HSL), copy-on-click with a
small toast. Use it everywhere hashes appear (this stream + 2-4).

### `ScriptOriginChip`

Just renders `basename(script)` with a `<details>`-style hover for
the full path. Keep it small; the script field is `sys.argv[0]`,
which is sometimes a Python module name and sometimes a path —
handle both.

---

## Implementation pointers

- The summary endpoint already exists; add the new `invocations`
  data source from 1-3.
- For the deterministic hash → color helper, run a stable hash
  (e.g. `simple-hash` or just take the first 3 hex chars of the
  hash and treat as HSL hue): same hash always yields same color.
- TanStack Table or react-virtuoso for the invocations table.
  Don't roll your own virtualization.
- For relative timestamps, `date-fns/formatDistanceToNow` is fine;
  re-render every 5s while live.
- Empty state: when there are zero invocations yet, show the
  agent identity card and a "waiting for first invocation"
  placeholder for the table.

---

## Be creative

- The brief enumerates the obvious columns; you can add more if
  the data is there. Examples worth considering: cassette
  hit/miss indicator, retry count (`metadata.retries`), input
  truncation hint when input is huge.
- Dense data calls for restraint. Don't fight a long row count
  with deeper styling — fight it with virtualization, smarter
  defaults (collapse old invocations into a "show 23 more" group),
  or distribution sparklines that summarise hundreds of rows in
  a glance.
- `hash_prompt` color-coding is the load-bearing UX trick here.
  Tune it carefully: too few colors → false collisions; too many →
  visual noise. Consider a "drift detected" highlight when two
  consecutive rows differ.
- Hover-row preview should feel snappy. Pre-render the IO popup
  the moment a row is hovered.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open a non-algorithm run; the header should render with all
# columns; clicking a row should call openDrawer (no-op until 2-3
# wires content; drawer should still slide in empty).
```
