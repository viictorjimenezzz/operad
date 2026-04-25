# operad-dashboard

Local-first web dashboard for [operad](../../README.md): live event
stream, agent graph (Mermaid, lazy-loaded), per-algorithm panels
(fitness curves, mutation heatmap, training progress, prompt drift,
debate rounds, beam candidates), and JSONL trace replay.

The frontend is the React 19 SPA in [`apps/frontend/`](../frontend/),
shared with `operad-studio`. The Python side is FastAPI + SSE; the
SPA bundle is built once and served from `operad_dashboard/web/`.

## Install

For local dev (from the operad repo root):

```bash
uv pip install -e apps/dashboard/
make build-frontend          # one-shot SPA build into operad_dashboard/web
```

Once published:

```bash
uv add 'operad[dashboard]'
```

## Run

### Live mode (in-process)

```bash
operad-dashboard --port 7860
```

Then in the same Python process, build and invoke an operad agent.
The dashboard auto-registers a `WebDashboardObserver` on
`operad.runtime.observers.registry`, so every event flows in.

### HTTP-attach mode (separate processes)

```bash
# terminal A
operad-dashboard --port 7860

# terminal B (your script)
import operad
operad.dashboard.attach(port=7860)
# ... run your agent normally ...
```

The `attach()` helper installs an HTTP-forwarding observer that POSTs
each event to the dashboard's `/_ingest` endpoint.

### Replay a JSONL trace

```bash
operad-dashboard --replay run.jsonl --speed 0
```

`--speed 0` plays as fast as possible; `--speed 1.0` honours the
recorded inter-event timestamps. The replay path is the canonical
offline mode — no LLM server required.

### Frontend dev loop

```bash
# terminal A: backend
make dashboard

# terminal B: vite dev server with HMR (proxies /runs, /stream, etc. to :7860)
make dev-frontend
```

Open http://localhost:5173/index.dashboard.html.

## What you see

- **Topbar** — global stats (runs, live, ended, errors, events,
  tokens, cost) and connection status badge.
- **Left sidebar** — list of runs with filter chips
  (all / algorithms / agents).
- **Run detail** — algorithm-specific layout chosen from
  `apps/frontend/src/layouts/`:
  - `EvoGradient` — fitness curve (best/mean/worst), population
    scatter, mutation heatmap, op success table.
  - `Trainer` — progress bars (epoch + batch + ETA), loss curve,
    drift timeline.
  - `Debate` — per-round score bars.
  - `Beam` — candidate scatter + top-K table.
  - default fallback — overview KPIs, agent graph, event timeline,
    raw envelope.

## API surface (preserved)

The Python API is the wire contract for both the SPA and any external
consumer:

- `GET /runs` — `RunSummary[]`
- `GET /runs/{id}/summary` — `RunSummary` (with `cost`)
- `GET /runs/{id}/events?limit=N` — buffered envelopes
- `GET /graph/{id}` — `{mermaid: string}`
- `GET /runs/{id}/{fitness,mutations,drift,progress}.json` and `.sse`
- `GET /stats`, `GET /evolution`
- `GET /stream` — multiplexed SSE (`agent_event`, `algo_event`,
  `slot_occupancy`, `cost_update`, `stats_update`)
- `POST /_ingest` — HTTP-attach ingestion
- `GET /api/manifest` — `{mode, version, langfuseUrl}` for the SPA

Frontend types mirror these shapes via Zod schemas in
[`apps/frontend/src/lib/types.ts`](../frontend/src/lib/types.ts).

## Out of scope

No auth, no DB persistence, no multi-user collab. Persistence:
point `OPERAD_TRACE=run.jsonl` at your run and replay later.
