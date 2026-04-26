# 3-1 Drawer views: Langfuse embed + filtered events

## Scope

Ship two drawer views: an embedded Langfuse trace iframe, and a
component-filtered event timeline. These are the two cheapest
high-value drawer views — get them in fast.

### You own

- `apps/frontend/src/components/agent-view/drawer/views/langfuse/`
  - `langfuse-embed.tsx`
  - `index.ts` — registers the view via
    `registerDrawerView("langfuse", …)`.
- `apps/frontend/src/components/agent-view/drawer/views/events/`
  - `filtered-events.tsx`
  - `event-row.tsx` (or reuse the existing event-row from the
    panels migration in 1-1)
  - `index.ts` — registers `"events"`.

### Depends on (iter-2 contracts)

- `registerDrawerView(kind, view)` from 2-3.
- `useUIStore.drawer.payload` carrying `agentPath` (and
  optionally `runId`).
- `GET /runs/{id}/agent/{path}/events` (1-3) for the filtered
  events view.
- The dashboard manifest `langfuseUrl` (already exposed at
  `/api/manifest`).

### Out of scope

- Other drawer views (3-2, 3-3).
- Drawer shell (2-3).

---

## Vision

The user clicks "Langfuse" or "Events" from an agent edge popup.
The drawer snaps open. They see exactly what they expected, with
zero context-switching.

### Langfuse view

- An iframe pinned to `${LANGFUSE_PUBLIC_URL}/...` with a URL that
  depends on payload:
  - If `payload.invocationId` is set → load
    `${LANGFUSE_PUBLIC_URL}/trace/${invocationId}` (the run-id is
    the trace id; an invocation-level deep-link is the same root
    trace; if Langfuse exposes per-span deep-links, use them).
  - Else if `payload.agentPath` is set → load
    `${LANGFUSE_PUBLIC_URL}/traces?search=${urlencoded(agentPath)}`
    (filtered traces list).
  - Else → load the bare Langfuse home.
- Above the iframe, a thin toolbar:
  - "Open in Langfuse" external-link button.
  - Path chip (read-only).
  - Refresh button.
- If `LANGFUSE_PUBLIC_URL` isn't configured, show a clean empty
  state with a link to `apps/README.md#self-hosted-observability-stack`.

### Filtered events view

- Hits `GET /runs/{runId}/agent/{path}/events`.
- Renders a virtualized list of events using the same row design
  as the existing event timeline (port the styling from 1-1's
  migrated panel; don't reinvent).
- Each row: kind chip (start/end/chunk/error), relative
  timestamp, latency (for end events), summary preview (input or
  output stringified to ~120 chars).
- Click a row → expand inline with full JSON view (or open a
  nested popover; your call).
- Header: count + "live" indicator (events arriving via the SSE
  stream are appended; ingest from `useEventBufferStore` filtered
  by `agent_path`).
- Toolbar:
  - Kind filter (start/end/chunk/error chips).
  - "Jump to invocation #N" if invocations are sparse.
  - Search input.

---

## Implementation pointers

- The iframe needs a sandbox attribute and `referrerpolicy`. Don't
  pass cookies you don't need to.
- For Langfuse to render inside an iframe, the public URL must
  not set `X-Frame-Options: deny`. Self-hosted Langfuse v3 ships
  with `same-origin` by default. If iframe-embedding fails, fall
  back to a "click to open" card.
- Filtered events view: the simplest impl is a hook
  `useFilteredEvents(runId, path)` that subscribes to
  `useEventBufferStore` and filters by `agent_path`. The
  endpoint hit is for archived/cold runs.
- Reuse virtualization (TanStack Virtual / react-virtuoso) — the
  events list can be very long.

---

## Polish targets

- Iframe loading state: skeleton while it loads, "open
  externally" link if it 404s.
- Live indicator on filtered events: pulse when a new event
  arrives during streaming.
- Event row preview: truncate cleanly, monospace, syntax-color
  JSON keys.
- Each event row shows the underlying envelope hash chip in the
  far right so users can correlate with the fingerprint card.

---

## Be creative

- Consider a "split mode" that shows Langfuse and filtered events
  side-by-side in the drawer when it's wide enough. The drawer
  shell is resizable; this is a nice power-user feature.
- For events, render chunk events as a single "streaming
  envelope" group rather than N rows. The user wants signal, not
  noise.
- Add a "open all events on Langfuse" shortcut from the events
  view.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open an agent run. Click an agent edge popup → "Langfuse" → drawer
# shows the iframe and toolbar. Click "Events" → drawer shows the
# filtered events list with kind filters and live updates.
```
