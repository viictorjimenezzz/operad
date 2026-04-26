# 3-3 Drawer view: per-attribute value timeline

## Scope

The per-field "what values has this attribute taken across every
invocation?" view. The user clicks the "values" link on a field
row in an I/O type popup (2-2) and lands here.

### You own

- `apps/frontend/src/components/agent-view/drawer/views/values/`
  - `value-timeline.tsx` — the drawer view.
  - `value-row.tsx` — one row per invocation (timestamp + value
    preview).
  - `value-detail.tsx` — full detail panel for the selected
    value (JSON tree for nested types, syntax-coloured text for
    strings).
  - `value-distribution-summary.tsx` — top-of-drawer mini
    distribution (numeric histogram / categorical top-N) — reuse
    the `ValueDistribution` component from 2-4 if applicable.
  - `index.ts` — registers `"values"`.

### Depends on (iter-1 contracts)

- `GET /runs/{id}/agent/{path}/values?attr=&side=` (1-3) — the
  timeline payload.
- `useUIStore.drawer.payload = {agentPath, attr, side}` (2-3).
- `ValueDistribution` from 2-4.

### Out of scope

- Mutating values, replaying — out of scope. This is a
  view-only.

---

## Vision

A user is debugging why an agent gave wrong answers. They open
the I/O popup for the input type, click "values" next to the
`question` field. The drawer pops open showing a list of every
question that was passed to this agent:

```
┌─ Values of `question` (input · str) ──────────────────────┐
│ Distribution: [ chart ]                                   │
│ 17 invocations · 12 unique values · most common "what is..│
├───────────────────────────────────────────────────────────┤
│ #1  3m ago     "what is the capital of France?"            │
│ #2  3m ago     "who built the Eiffel Tower?"               │
│ #3  2m ago     "what is the capital of Germany?"           │
│ ...                                                       │
└───────────────────────────────────────────────────────────┘
```

- Top: distribution summary (the same ValueDistribution chart
  from 2-4 — numeric / categorical adapt automatically).
- List: virtualized rows of `(invocationId, started_at,
  preview-of-value)`. Click a row to expand into the
  `value-detail` panel below.
- Each row has actions:
  - **Open invocation** → shifts the drawer to the events view
    (3-1) filtered around that invocation.
  - **Find similar** — filters the list to values within a
    similarity threshold (text: substring match; numeric: range).
  - **Copy** — copy the raw value.
- Toolbar above the list:
  - Switch input ↔ output (the drawer payload tells you which
    side, but the user may want to flip).
  - Search / filter values.
  - Sort by time / frequency / length.

For complex types (nested Pydantic models, lists, dicts), the
preview truncates with a "show more" expander; the detail panel
shows a JSON tree with collapsible nodes (reuse the existing
JSON view from the panels migration).

---

## Implementation pointers

- The `ValueDistribution` component (from 2-4) handles
  numeric/categorical heuristics. Pass it the raw values array.
- For string types, render with a small monospace font and
  preserve newlines on hover.
- For lists/objects, show length + first few keys/items in the
  preview row, full tree in the detail panel.
- Endpoint pagination — consider implementing cursor-based
  pagination if the timeline is huge. For v1, just trust the
  endpoint's default limits.
- Streaming: subscribe to `useEventBufferStore` and prepend new
  values as they arrive on the live run.

---

## Polish targets

- "Invocation #N" links should be deeplinks: clicking should set
  some "selected invocation" state in `useUIStore` (or via URL
  search param) so the metadata table (2-1) and the graph (2-2)
  also highlight that invocation.
- Distribution chart: switch axes for numeric (histogram vs
  cumulative); for categorical, show top-N + "rest".
- Color the value preview rows by similarity (consecutive equal
  values share a subtle background hue, so repeats are obvious).
- Empty state: "no invocations yet for this attribute".

---

## Be creative

- "Outlier highlight" — flag values that differ markedly from
  the distribution (numeric: >2σ; categorical: rare values <5%
  frequency).
- A side-by-side diff between two values (select-with-checkboxes
  → "diff" button → shows a structural diff inline).
- For string values, show a small "tokens" count next to each
  row (cheap heuristic, e.g. word count / 0.75).
- Treat outputs differently from inputs: outputs sometimes carry
  a confidence / score field that's worth surfacing
  alongside the value.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open an agent run. Click an I/O type node → expand to the field
# popup → click "values" on a field with multiple historical values.
# - Drawer opens with distribution summary.
# - Rows render with preview + timestamps; click expands the detail.
# - Switch side (input ↔ output) works.
# - Open-invocation links shift the drawer to the events view.
```
