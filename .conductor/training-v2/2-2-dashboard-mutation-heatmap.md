# 2-2 — Dashboard mutation-activity heatmap

**Wave.** 2. **Parallel with.** 2-{1,3..5}. **Depends on.** 1-1.

## Context

After 1-1 ships, `generation` events carry `op_success_counts` and
`op_attempt_counts`. A heatmap (gen × op) of success rate shows at a
glance which mutations are pulling their weight and which are dead
weight — great debugging UX for tuning the mutation set.

## Scope — in

### `apps/dashboard/operad_dashboard/routes/mutations.py` (new)

- `GET /runs/{run_id}/mutations.json` — returns
  `{gens: list[int], ops: list[str], success: list[list[float]],
    attempts: list[list[int]]}` — two matrices aligned by `gens` × `ops`.
  Derive `success_rate = success / attempts` (guarding for zero).
- `GET /runs/{run_id}/mutations.sse` — SSE of new generations only.

### `apps/dashboard/operad_dashboard/templates/partials/_mutations.html` (new)

- Render a Chart.js matrix/heatmap plugin, OR a plain HTML table
  with color-tinted cells (e.g., `rgba(34,197,94, success_rate)`).
  The HTML table is simpler, no extra dep; go with that.
- Rows = ops; columns = generations; cell content = `success_rate`
  (formatted as `0.83` with 2 decimals); cell background color
  scales with rate. Add a small tooltip on hover: "3/5 attempts."

### `apps/dashboard/operad_dashboard/static/js/mutations.js` (new)

- EventSource listener; on each new event, append a column to the
  rendered table and re-tint existing cells if needed.
- Handles the case where new ops appear mid-run (uncommon but
  possible if user registers new mutations between generations).

### `apps/dashboard/operad_dashboard/app.py`

- Include the router; embed `_mutations.html` below `_fitness.html`
  in run-detail.

### Tests

`apps/dashboard/tests/test_mutations.py`:

- Seed 2 `generation` events with mock counts; hit `/mutations.json`;
  verify matrices align.
- Missing payload keys → endpoint returns `{gens: [], ops: [], ...}`
  (graceful empty state, no 500).

## Scope — out

- Do not introduce a full matrix-plotting library.
- Do not correlate mutations across runs (single-run view only).

## Dependencies

- 1-1 payload extensions (`op_success_counts`, `op_attempt_counts`).
- Existing per-run event store in dashboard.

## Design notes

- **Backward compat.** If a run predates 1-1, counts are absent;
  endpoint returns empty matrices and the template hides the panel.
- **Per-op ordering.** Sort ops by total attempts descending so the
  most-used ops stay at the top — makes the heatmap read left-to-
  right like a ranking.
- **Color scale.** `rgba(34,197,94, α)` where α = success_rate;
  red-tinted when rate == 0 (`rgba(239,68,68, 0.8)`) to make
  dead-weight ops obvious.
- **Accessibility.** Keep text readable; don't rely on color alone
  for rate info.

## Success criteria

- `pytest apps/dashboard/tests/test_mutations.py` passes.
- Running `examples/talker_evolution.py --dashboard` shows both
  panels (fitness + mutations) populated.
- Dead-weight ops (zero successes) render clearly as red cells.
- Old runs without attribution data show empty-state / hidden panel.
