# 1-3 Dashboard backend: per-agent endpoints

## Scope

You are adding the FastAPI routes the new agent view will read
from. Pure additive backend work — frontend (1-1) and operad core
(1-2) are independent siblings.

### You own

- `apps/dashboard/operad_dashboard/agent_routes.py` (new) — all
  per-agent endpoints below.
- `apps/dashboard/operad_dashboard/app.py` — mount the new router.
- `apps/dashboard/operad_dashboard/runs.py` — extend `RunInfo` with
  whatever bookkeeping is needed (e.g. invocation index by
  `agent_path`). Keep existing fields backwards-compatible *within
  this PR's scope* (other dashboard code reads `RunInfo`); just
  don't keep dead state for old views.
- `apps/dashboard/tests/test_agent_routes.py` (new).

### Depends on

- **`operad.core.graph.to_io_graph(...)`** — a sibling stream (1-2)
  ships it. Import it and use it; don't stub. The signature is
  fixed in `1-2-graph-inversion.md` — code to that contract.

### Out of scope

- Frontend.
- Algorithm-specific endpoints (existing `/runs/{id}/fitness`,
  `/mutations`, etc. — leave those alone).

---

## Endpoints

All endpoints live under `/runs/{run_id}/...`. All return JSON.
All must:

1. Work for **live** runs (read from the in-memory `RunInfo`).
2. Work for **archived** runs (rehydrate from the archive store).
3. Return a clear 404 (with `{"error": "...", "reason": "..."}`)
   when the run, agent path, or attribute is unknown.
4. Be cassette-replayable for tests.

### `GET /runs/{run_id}/io_graph`

Calls `to_io_graph(run_info.graph)` and returns the result. If the
run has no graph yet (root start event hasn't arrived), return
`{"root": null, "nodes": [], "edges": []}` with HTTP 200 — the
frontend renders an empty-state.

### `GET /runs/{run_id}/invocations`

Returns the **root agent's** invocation list. One entry per
`(invoke_start, invoke_end)` pair on the root path:

```json
{
  "agent_path": "RootClass",
  "invocations": [
    {
      "id":                "<invocation id; use envelope.run_id or a stable derivation>",
      "started_at":        1714200000.0,
      "finished_at":       1714200001.2,
      "latency_ms":        1234.5,
      "prompt_tokens":     820,
      "completion_tokens": 412,
      "hash_prompt":       "1a2b3c4d…",
      "hash_input":        "9f8e7d6c…",
      "hash_content":      "0011aabb…",
      "status":            "ok" | "error",
      "error":             "<repr if status == error>" | null,
      "langfuse_url":      "<full deeplink>" | null,
      "script":            "<sys.argv[0] from start metadata>" | null
    }
  ]
}
```

`langfuse_url` should be `${LANGFUSE_PUBLIC_URL}/trace/{run_id}`
(use the manifest's configured public URL; null if unconfigured).

### `GET /runs/{run_id}/agent/{path}/meta`

Per-component metadata bundle. `path` is dotted (`Root.stage_0`).
URL-encode dots if needed.

```json
{
  "agent_path":   "Root.stage_0",
  "class_name":   "Reasoner",
  "kind":         "leaf" | "composite",
  "hash_content": "...",
  "role":         "...",
  "task":         "...",
  "rules":        ["...", "..."],
  "examples":     [{"input": {...}, "output": {...}}],
  "config": {
    "backend": "openai",
    "model":   "gpt-4o-mini",
    "sampling":  {...},
    "resilience": {...},
    "io":         {...},
    "runtime":    {...}
  },
  "input_schema":  {<from to_io_graph node>},
  "output_schema": {<from to_io_graph node>},
  "forward_in_overridden":  true | false,
  "forward_out_overridden": true | false,
  "trainable_paths": ["role", "task", "rules", "examples", "config.sampling.temperature", ...],
  "langfuse_search_url": "${LANGFUSE_PUBLIC_URL}/traces?search=<urlencoded path>" | null
}
```

`forward_in_overridden` is `type(agent).forward_in is not Agent.forward_in`.
`trainable_paths` enumerates `requires_grad=True` parameters.

### `GET /runs/{run_id}/agent/{path}/invocations`

Same shape as the root invocations endpoint, but filtered to
events whose `agent_path == path`.

### `GET /runs/{run_id}/agent/{path}/prompts`

Rendered prompts across all invocations of this component:

```json
{
  "agent_path": "Root.stage_0",
  "renderer":   "xml" | "markdown" | "chat",
  "entries": [
    {
      "invocation_id": "...",
      "started_at":    1714200000.0,
      "hash_prompt":   "1a2b3c4d…",
      "system":        "<rendered system message>",
      "user":          "<rendered user message>"
    }
  ]
}
```

Compute live by replaying `agent._compose_system_for_call(x) +
"\n\n" + agent.format_user_message(x)` against each historic
input. If the live agent isn't reachable (archived run, agent
torn down), fall back to whatever was logged in the event
metadata (envelopes carry `hash_prompt` but not the prompt
text — note this in the response with a `"replayed": false` flag).

### `GET /runs/{run_id}/agent/{path}/values?attr=<name>&side=in|out`

Timeline of a single attribute across invocations:

```json
{
  "agent_path": "Root.stage_0",
  "attribute":  "question",
  "side":       "in",
  "type":       "str",
  "values": [
    {"invocation_id": "...", "started_at": 1714200000.0, "value": "what's the capital of France?"},
    {"invocation_id": "...", "started_at": 1714200005.4, "value": "what's the capital of Germany?"}
  ]
}
```

For complex attribute types (nested Pydantic models), embed the
full JSON-mode dump.

### `GET /runs/{run_id}/agent/{path}/events`

Filtered event list (envelopes with `agent_path == path`),
default limit=200, max=500. Same shape as
`/runs/{run_id}/events`.

---

## Implementation pointers

- The existing `RunInfo` (`apps/dashboard/operad_dashboard/runs.py`)
  already buffers events. Add an `events_by_agent_path: dict[str,
  list[Event]]` index that's updated on ingest.
- Live agents may be reachable via the dashboard's in-memory
  registry, or you may need to capture rendered prompts at ingest
  time. Decide based on what's already there. If you add ingest-time
  capture, make sure it's cheap and doesn't hammer the runner.
- Reuse the existing archive-rehydration helper for archived runs.
- For the per-attribute values endpoint, walk `event.input` /
  `event.output` (Pydantic models) via `model_dump(mode="json")`,
  then `getattr` / dict-access by the requested name.
- Langfuse URL composition: the manifest endpoint
  (`/api/manifest`) already returns `langfuseUrl`. Reuse the same
  config source.
- Don't paginate yet — limits are fine. We can add cursor pagination
  in a follow-up if dashboards lag on huge runs.

---

## Tests

`apps/dashboard/tests/test_agent_routes.py` — exercise every
endpoint with fixture envelopes:

- A live run with one root invocation.
- A live run with multiple invocations of the same agent.
- A live run where the agent's prompt changed between invocations
  (different `hash_prompt`).
- An archived run.
- A 404 on unknown path / attribute.
- A request for `side=in` on an attribute that only exists on
  output (and vice versa) — clear error.

Use FastAPI's `TestClient`. No live model calls.

---

## Be creative

- The endpoints above are a floor, not a ceiling. If you spot a
  natural next-of-kin (e.g. `/runs/{id}/agent/{path}/diff?from=A&to=B`
  for invocation-level structural diff), add it — but document the
  shape in this brief's "Endpoints" section so iter-3 / iter-4
  consumers know.
- Think about caching. Re-rendering prompts for every fetch is
  expensive on long runs. A per-`(run_id, path)` LRU cache keyed by
  the hash of historic inputs is reasonable.
- `/runs/{run_id}/io_graph` is hot-path data. SSE-stream graph
  topology updates if the graph changes mid-run? (Probably not — the
  graph is fixed at root-build time. Confirm and document either
  way.)

---

## Verification

```bash
uv run pytest apps/dashboard/tests/test_agent_routes.py -v
uv run pytest apps/dashboard/tests/ -q
make dashboard                                       # smoke
curl http://127.0.0.1:7860/runs/<some-id>/io_graph   # smoke
```
