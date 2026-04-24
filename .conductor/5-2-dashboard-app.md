# 5 · 2 — Dashboard app — `apps/dashboard/`

**Addresses.** A-2 — `RichDashboardObserver` is terminal-only with
no metrics, graph, or slot view. No shareable URL, no multi-run
history. VISION §7 names a live dashboard as an iteration-4 goal.
See [`../ISSUES.md`](../ISSUES.md) Group I.

**Depends on.**
- 4-1 (algorithm events) — the dashboard renders them.
- 4-2 (slot occupancy) — the slot panel polls it.
- 4-3 (cost observer) — the cost panel totals it.

**Blocks.** 6-1 (demos showcase) — `agent_evolution` launches the
dashboard for its fitness-curve story.

---

## Required reading

- `.conductor/wave-4-overview.md` §1 — library-vs-apps split. The
  dashboard is an **app** in `apps/dashboard/`; it **must not** live
  inside `operad/`.
- `operad/runtime/observers/base.py` — the event bus the dashboard
  subscribes to.
- `operad/runtime/events.py` — post-4-1 algorithm event schema.
- `operad/runtime/slots.py` — post-4-2 `occupancy()` API.
- `operad/runtime/cost.py` — post-4-3 `CostObserver`.
- `operad/runtime/trace.py` — `TraceObserver`, `Trace` for replay mode.
- `operad/core/graph.py` — `to_mermaid(graph)` — reused for the
  graph panel.
- `operad/runtime/trace_diff.py` — `_repr_html_` pattern to mimic.

---

## Goal

Ship a self-contained web app at `apps/dashboard/` that:

1. Renders the live event stream from a local operad run.
2. Shows the Mermaid-rendered agent graph per run.
3. Surfaces slot occupancy and cost totals.
4. Supports replay of a JSONL trace file via `--replay`.

Design: in-process FastAPI + SSE + htmx + Jinja + Mermaid.js. **No
React/Vite build step.** No bundler. `apps/dashboard/` imports
`operad` like any other downstream project.

## Scope

### New top-level folder: `apps/`

Create `apps/` at the repo root (sibling of `operad/`, `examples/`,
`tests/`). Add a one-paragraph `apps/README.md` explaining the purpose
(see `.conductor/wave-4-overview.md` §1 for text).

### New folder: `apps/dashboard/`

```
apps/dashboard/
  pyproject.toml          # separate project metadata
  README.md               # install + run instructions
  operad_dashboard/       # the Python package
    __init__.py
    app.py                # FastAPI factory: create_app(registry=...)
    observer.py           # WebDashboardObserver (pushes to queue)
    replay.py             # JSONL → event stream at recorded cadence
    cli.py                # `operad-dashboard` entry-point
    templates/
      index.html          # shell (Jinja + htmx + Mermaid.js)
    static/
      app.js              # SSE wiring (<100 lines)
      styles.css
  tests/
    test_app.py           # FastAPI TestClient hits /stream, /graph
    test_observer.py
    test_replay.py
```

`pyproject.toml` declares `operad` as a dependency (editable for local
dev) and pins `fastapi`, `uvicorn[standard]`, `jinja2`,
`sse-starlette`. Offers `pip install -e apps/dashboard/` for local
development and `pip install operad-dashboard` once published.

### FastAPI endpoints

- `GET /` — serves `index.html` shell.
- `GET /stream` — SSE. Yields every `AgentEvent` and
  `AlgorithmEvent` received by the observer, plus periodic
  `SlotOccupancy` snapshots (every 2s via `asyncio.sleep`) and
  `CostUpdate` snapshots (every 2s).
- `GET /graph/{run_id}` — returns the Mermaid source for the given
  run's `AgentGraph` as JSON `{mermaid: "..."}`.
- `GET /runs` — JSON array of active + terminated run_ids (last 50).
- `GET /static/app.js`, `GET /static/styles.css` — static assets.

Events serialised as one JSON object per SSE `data:` field:

```json
{"type": "agent_event", "kind": "end", "run_id": "abc", "agent_path": "Pipeline", ...}
{"type": "algo_event", "kind": "generation", "algorithm_path": "Evolutionary", "payload": {...}}
{"type": "slot_occupancy", "snapshot": [{"backend": "llamacpp", ...}]}
{"type": "cost_update", "totals": {"run_id_1": {"prompt_tokens": 1234, ...}}}
```

### `WebDashboardObserver`

A small `Observer` (same Protocol as `JsonlObserver`) that pushes each
event into a bounded `asyncio.Queue` (maxsize=1024, drop-oldest on
overflow). `GET /stream`'s generator drains this queue. One observer
serves N subscribers via a fan-out queue (use
`asyncio.Queue` + an async `pubsub`-style broadcaster).

### CLI: `operad-dashboard`

`apps/dashboard/operad_dashboard/cli.py`:

```
operad-dashboard [--host 127.0.0.1] [--port 7860] [--replay path.jsonl]
```

- Default (no `--replay`): starts `uvicorn` on the given port,
  attaches a `WebDashboardObserver` to `operad.runtime.observers.base.registry`,
  prints "Dashboard live at http://host:port; now run your agent in
  the same process or attach via `OPERAD_DASHBOARD=http://host:port`".

  Users run their agent in a separate terminal but within the same
  Python process is also fine — the in-process registry handles both.

  *Post-5-2 stretch:* a small `operad.dashboard.attach(port=7860)`
  helper in operad itself for the in-process case. If it's trivial,
  ship it as a 10-line function that calls urllib; otherwise defer.

- With `--replay path.jsonl`: loads the trace, pushes events through
  the observer at the recorded timestamps (or as fast as possible
  with `--speed 0`).

### Index HTML shell

Single-page HTML with three panels:

- **Left** — graph panel. Shows the Mermaid source for the currently
  selected run. Re-renders on run selection change.
- **Center** — event timeline. Each event is one htmx-swapped row.
  Algorithm events get a different background colour from agent
  events. Errors are red.
- **Right** — metrics panel. Three sub-cards: active runs, slot
  occupancy table, cost totals table.

Use Mermaid.js via a single CDN script tag (`<script
src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js">`) or
bundled vendor copy — user's choice. htmx via CDN is standard.

### Dashboard extra in operad

In operad's `pyproject.toml`, add `[project.optional-dependencies]`:

```toml
dashboard = ["operad-dashboard"]
```

— so `uv add 'operad[dashboard]'` pulls in the sibling app once
published. In dev, users run `uv pip install -e apps/dashboard/`
directly.

---

## Verification

- Unit test: construct `create_app()` with a canned `WebDashboardObserver`;
  use `TestClient` to hit `GET /runs`, `GET /stream` (read first
  event), `GET /graph/<run_id>`. Assert JSON shape.
- Manual smoke: `operad-dashboard --port 7860` in one terminal, run
  `demos/agent_evolution/run.py` (brief 6-1) in another, open
  `localhost:7860` and verify live updates.
- Replay smoke: create a JSONL trace via `JsonlObserver`, run
  `operad-dashboard --replay path.jsonl --speed 0`, watch events
  replay.
- Offline safety: the dashboard must work with no LLM server
  reachable — the replay mode is the canonical offline path.

---

## Out of scope

- Authentication / multi-tenant. Local-first.
- Database persistence. In-memory ring buffer of last 50 runs. If a
  user wants persistence, they point `OPERAD_TRACE=run.jsonl`.
- React/Vue/Svelte. No JS build pipeline.
- Real-time multi-user collaboration.
- Embed-in-Jupyter mode. `AgentGraph._repr_html_` and
  `TraceDiff._repr_html_` already cover the notebook path.

---

## Design notes — library-vs-apps discipline

- **No code in `operad/runtime/dashboard/`.** The observer base +
  event schema + slot API + cost observer all live in operad already
  (from briefs 4-1/4-2/4-3). This brief adds the *consumer* in
  `apps/dashboard/`.
- Do not add a mandatory `fastapi` dependency to `operad` itself. The
  `[dashboard]` optional extra references the sibling app.
- If you find yourself wanting a primitive that belongs inside operad
  (e.g. a general "event broadcaster" that's not web-specific), add
  it to operad *first* via a focused commit, then consume it from the
  app. Don't reach into operad internals from the app code.
- Keep the app's Python surface small — `operad_dashboard.create_app`,
  `operad_dashboard.WebDashboardObserver`, `operad_dashboard.replay`.
  Nothing more needs to be public.
