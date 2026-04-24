# 2-1 — Dashboard fitness-curve panel

**Wave.** 2. **Parallel with.** 2-{2..5}. **Depends on.** (nothing hard; uses existing `generation` events).

## Context

`EvoGradient` emits `generation` events with `population_scores`. The
web dashboard logs them but doesn't plot them. Add a live chart of
best-so-far and population mean over generations.

## Scope — in

### `apps/dashboard/operad_dashboard/routes/fitness.py` (new)

- A FastAPI router exposing:
  - `GET /runs/{run_id}/fitness.json` — returns a JSON array of
    `{gen_index, best, mean, population_scores, timestamp}`,
    assembled from the stored events for that run.
  - `GET /runs/{run_id}/fitness.sse` — SSE endpoint streaming one
    event per new `generation` entry.

### `apps/dashboard/operad_dashboard/templates/partials/_fitness.html` (new)

- A Jinja partial, included from the existing run-detail template,
  containing a `<canvas>` sized ~480×240 and a minimal script tag
  that imports Chart.js (CDN) and renders:
  - a solid line for best-so-far,
  - a dashed line for population mean,
  - a faint shaded band of population-score spread (min/max).

### `apps/dashboard/operad_dashboard/static/js/fitness.js` (new)

- Opens an EventSource on `/runs/{run_id}/fitness.sse`, updates the
  Chart.js data arrays on each message, calls `chart.update()`.
- Handles disconnect / reconnect cleanly.

### `apps/dashboard/operad_dashboard/app.py`

- Include the new router: `app.include_router(fitness.router)`.
- Include `_fitness.html` in the run-detail template at a clear
  anchor (below the event timeline or to its right — match what
  exists).

### Tests

`apps/dashboard/tests/test_fitness.py`:

- Unit-test the `/fitness.json` endpoint: seed the in-memory run
  store with 3 `generation` events and confirm the response has 3
  entries in ascending `gen_index` order.
- Unit-test the SSE endpoint: push a new event and confirm the
  client receives it within 2 seconds.

## Scope — out

- Do not replace the existing event timeline — add the chart
  alongside.
- Do not add a download/export button. Users can hit the JSON
  endpoint directly.
- Do not introduce a heavy charting library (D3, Vega). Chart.js
  only; loaded from CDN like Mermaid.js already is.

## Dependencies

- Existing: `WebDashboardObserver`, per-run event store,
  `AlgorithmEvent(kind="generation")` with `population_scores`.

## Design notes

- **CDN import.** Already the repo convention (mermaid.js is CDN).
  Keep `Chart.js` CDN-loaded; falls back to a plain `<pre>` dump of
  the JSON if Chart.js fails to load (no hard dep).
- **Backwards-compat for old events.** If `population_scores` is
  missing, skip the mean/spread rendering — just plot `best`.
- **Run-scoped.** One chart per run. If no `generation` events,
  hide the panel entirely.
- **No persistence layer changes.** Reuse the existing in-memory
  per-run event store.

## Success criteria

- Start `operad-dashboard --port 7860`, run
  `examples/talker_evolution.py --dashboard`. The fitness panel
  renders and updates live.
- `pytest apps/dashboard/tests/test_fitness.py` passes.
- `uv run ruff check apps/dashboard/` clean.
- Navigating to an older run with no `generation` events doesn't
  crash the page (panel is hidden).
