# operad-dashboard

Local-first web dashboard for [operad](../../README.md): live event
stream, agent graph (rendered with Mermaid.js), slot occupancy, cost
totals, and JSONL trace replay. Runs as a small FastAPI + SSE + htmx
process — no JS build step, no React.

## Install

For local dev (from the operad repo root):

```bash
uv pip install -e apps/dashboard/
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

## What you see

- **Left** — the agent graph for the currently selected run, rendered
  via Mermaid.js (CDN-loaded, so the graph panel needs network).
- **Center** — live event timeline. Algorithm events have a tinted
  background; errors are red.
- **Right** — three cards: active runs, slot occupancy snapshot,
  cost totals (per `run_id`).

## Out of scope

No auth, no DB persistence, no React build pipeline, no multi-user
collab. Persistence: point `OPERAD_TRACE=run.jsonl` at your run and
replay later.
