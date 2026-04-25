# 1-2 — Dashboard backend hardening

> **Iteration**: 1 of 4. **Parallel slot**: 2.
> **Owns**: the entire `apps/dashboard/operad_dashboard/` package.
> **Forbidden**: `operad/`, `apps/frontend/`, `apps/dashboard/Dockerfile`.

## Problem

The dashboard backend has four issues that compound into "not usable":

1. **Run flood**: every inner `Agent.forward` invocation registers as
   its own root run. A 6-generation demo created 100 runs (97 noise +
   3 genuine algorithm runs). The runs list became a wall of hex IDs.

2. **Legacy HTML fallback**: `app.py` returns an inline HTML template
   when the SPA bundle is missing. Today the SPA is *always* missing
   (see task 1-3). Result: users see a thin static page with
   EvoGradient-shaped tabs hardcoded.

3. **Missing `/api/manifest`**: the SPA expects this endpoint; it
   returns 404 today.

4. **No graph for HTTP-attach runs**: graph tab always says "no graph
   captured" because the HTTP forwarder doesn't push it. Task 1-1
   defines a new `graph_envelope`; this task wires up the receiving
   side.

## Scope

### Owned files

- All of `apps/dashboard/operad_dashboard/`:
  - `app.py` (FastAPI app, routes, ingest, manifest)
  - `runs.py` (RunRegistry, RunInfo, parent_run_id linkage, synthetic flag)
  - `observer.py` (event serialization)
  - `replay.py`
  - `cli.py`
  - `routes/` — all aggregation endpoints
- All of `apps/dashboard/tests/`.

### Forbidden files

- `operad/dashboard.py` and anything in `operad/runtime/` (1-1's domain).
- `apps/frontend/` (frontend agents own this).
- `apps/dashboard/Dockerfile` (1-3's domain).

## Direction

### Synthetic run flagging

Once 1-1 lands, every `AgentEvent` whose root invocation happened
inside an algorithm context will carry
`metadata.parent_run_id: str | None`.

- `RunInfo` gets a `parent_run_id: str | None = None` and a
  `synthetic: bool = False` field.
- On first event ingest for a run_id, if the event has
  `parent_run_id`, mark the run synthetic and link it to the parent.
- `/runs` returns only non-synthetic runs by default; expose
  `?include=synthetic` to bypass.
- New endpoint: `GET /runs/{run_id}/children` returns the list of
  synthetic children for a parent algorithm run.
- New endpoint: `GET /runs/{run_id}/parent` returns the parent run's
  summary (or 404 if not synthetic).

Decide whether to also expose a tree endpoint
(`GET /runs/{run_id}/tree` returning the whole subtree). Likely yes —
the SPA will want it for the algorithms grouping view in task 2-1.

### Defensive ingest

Be lenient on what `/_ingest` accepts:

- A single envelope or a JSON array of envelopes (1-1 will start
  batching).
- A `graph_envelope` kind that populates the run's mermaid cache used
  by `/graph/{run_id}`.
- Reject unknown `type` fields with a clear 422 message — don't
  silently drop.

### `/api/manifest`

Return:

```json
{
  "mode": "production" | "development",
  "version": "<package version>",
  "langfuseUrl": "<env var or null>"
}
```

Read `LANGFUSE_PUBLIC_URL` from environment. Default to `null`. The
SPA will use this to render the "View in Langfuse" deep links.

### Kill the legacy HTML

Today `app.py` likely has a multi-line inline `_INDEX_HTML` constant
served at `GET /`. After this task:

- `GET /` serves `web/index.dashboard.html` from the bundled SPA.
- If `web/index.dashboard.html` is missing at startup, **fail fast**:
  log an actionable error ("`make build-frontend` was not run before
  starting the dashboard") and either exit non-zero or serve a
  503-like placeholder page that explains the problem.
- Mount the SPA's static assets directory (`web/assets/` or whatever
  Vite produces) under a stable path; the SPA references its own
  bundle paths so this is mostly `StaticFiles(directory=...,
  html=False)`.
- Delete the inline `_INDEX_HTML` and `_INDEX_CSS` constants entirely.

### Run registry hygiene

While you're in `runs.py`:

- The default cap of 200 runs is fine; surface it as a constructor
  arg.
- Add a `clear()` method (used by tests + 4-4 will need it).
- Consider an `algorithm_kinds: list[str]` field on `RunInfo` if not
  already there — useful for the SPA's algorithm grouping.
- Don't add persistence — that's 4-4. Keep it in-memory.

### What `/runs` returns

The current shape is a flat list of summaries. Keep that, but:

- Add `parent_run_id: str | None`, `synthetic: bool`, and
  `algorithm_class: str | None` (parsed from `algorithm_path`).
- Sort: most-recent-started first, with synthetic runs hidden by
  default.

## Acceptance criteria

1. After 1-1 + 1-2 land, running the agent_evolution demo produces:
   - **Exactly one** non-synthetic run in `/runs`.
   - That run has `algorithm_path="EvoGradient"`, `state="ended"`,
     `event_total >= 8` (start + 6 generation + end).
   - `/runs/{id}/children` returns the 96 synthetic children.
2. `/api/manifest` returns the manifest JSON.
3. `/_ingest` accepts both single envelopes and arrays.
4. `/_ingest` accepts `graph_envelope` and stores the mermaid in the
   run's graph cache; `/graph/{run_id}` returns it.
5. Starting the dashboard without a `web/` directory exits with a
   clear error message (or serves a placeholder; pick the simpler
   option, document the choice).
6. Tests under `apps/dashboard/tests/`:
   - `test_synthetic_run_filtering.py`
   - `test_manifest.py`
   - `test_graph_envelope.py`
   - `test_batch_ingest.py`

## Dependencies & contracts

### Depends on

- Task 1-1 will provide `parent_run_id` in event metadata. Until 1-1
  lands you can simulate it in tests by hand-crafting envelopes.

### Exposes

- `GET /runs?include=synthetic` (default excludes synthetic).
- `GET /runs/{id}/children` and `GET /runs/{id}/parent`.
- `GET /api/manifest`.
- `POST /_ingest` accepts arrays and `graph_envelope`.
- SPA at `web/index.dashboard.html` is mandatory.

## Risks / non-goals

- Don't add persistence.
- Don't change the SSE event schema beyond what's documented above.
  The `algo_event` and `agent_event` shapes that already exist are
  load-bearing for the SPA.
- Don't add authentication or CORS hardening — local-first, dev tool.
- Don't introduce a templating engine for the served HTML; just
  `FileResponse(web/index.dashboard.html)`.

## Verification checklist

- [ ] Demo run produces 1 non-synthetic run; children endpoint
      returns the rest.
- [ ] `curl http://localhost:7860/api/manifest` returns valid JSON.
- [ ] Dashboard fails clearly when `web/` is missing.
- [ ] All `apps/dashboard/tests/` pass with `cd apps/dashboard && uv
      run pytest`.
- [ ] No regressions: `make test-dashboard` passes.
- [ ] Module docstring at the top of `runs.py` documents the
      synthetic-run model.
