# 1-1 — Operad → dashboard transport reliability

> **Iteration**: 1 of 4 (foundation). **Parallel slot**: 1.
> **Owns**: `operad/dashboard.py` and adjacent runtime plumbing.
> **Forbidden**: anything under `apps/`.

## Problem

Real demos drop most events on their way to the dashboard. Empirical
test on 2026-04-25:

- `agent_evolution` demo emits 6 `generation` events to its local JSONL
  trace.
- Only `gen_index=5` (the last one) reached the dashboard registry.
- The parent `EvoGradient` run was stuck `state="running"` because the
  `algo_end` event was also lost.
- The Mermaid graph for the run never reached the dashboard at all
  (graph tab always shows "no graph captured").

Likely root causes (verify before assuming):

1. `_HttpForwardObserver.on_event` in `operad/dashboard.py` is `async
   def`. POSTs are issued and not awaited at process exit — when the
   demo's event loop shuts down, in-flight requests are cancelled.
2. The HTTP forwarder has no `attach()` teardown hook.
3. Inner `Agent.forward` calls (e.g. each scoring inside an algorithm)
   register as their own root runs, polluting `/runs` (97 noise rows
   from a 6-gen demo). They should logically be children of the
   algorithm's run.
4. The agent graph is never POSTed; only inline observers see it.

## Scope

### Owned files

- `operad/dashboard.py` — the HTTP-forwarder observer and `attach()`.
- `operad/runtime/observers/base.py` — only if the registry needs a
  shutdown hook (likely yes).
- New: `operad/utils/run_context.py` (or similar) for a
  `current_run_id` contextvar if you go that route.
- Tests under `tests/runtime/` and `tests/dashboard/` (new file is fine).

### Forbidden files

- Anything under `apps/dashboard/` — that's task 1-2's territory.
- Anything under `apps/frontend/`.
- `operad/algorithms/` — algorithm internals shouldn't change to
  accommodate transport.

## Direction (hints, not a recipe)

### Reliable transport

- Replace fire-and-forget POSTs with a bounded `asyncio.Queue` + a
  dedicated background task that drains the queue and POSTs in batches.
- Register a teardown hook in `attach()` (atexit, `asyncio.shield`, or
  a signal handler) that flushes the queue **synchronously** before
  process exit. The user-facing contract: "if your demo printed
  'finished', the dashboard has all your events."
- Consider batching: collect events for ≤50ms or up to N events, POST
  as `[envelope, envelope, ...]`. Backend must accept either a single
  envelope or a list. (Coordinate the contract change with task 1-2.)
- Handle `httpx.HTTPError` / `urllib.error.URLError` with bounded
  retries + exponential backoff; never block the calling agent.

### Parent-run linkage

The cleanest fix for the run-flood is **NOT** to suppress events but
to mark inner runs as children of the algorithm's run.

- When an algorithm enters `_enter_algorithm_run()` (look at how it's
  defined in `operad/runtime/observers/base.py` or wherever
  algorithm-event emission lives), set a `current_algorithm_run_id`
  contextvar.
- Every `AgentEvent` emitted while that var is set carries the
  algorithm's run_id in its `metadata.parent_run_id` field.
- Top-level child agents do NOT inherit the parent's run_id directly
  (we want distinct `run_id`s so per-individual events stay separate),
  but they tag themselves so the dashboard can group.

Decision tradeoff for you to make: a) inherit parent run_id (one big
run with many agent_paths) — simpler, but loses per-individual run
identity; b) keep distinct run_ids + parent_run_id metadata — more
work but preserves the granularity. **Recommend (b)** because cassette
replay and per-individual debug benefit from distinct IDs.

### Graph capture

- Define a new envelope kind `graph_envelope` (or reuse an existing
  metadata field, but a distinct kind is clearer):

  ```json
  {
    "type": "graph_envelope",
    "run_id": "...",
    "mermaid": "flowchart LR\n  A --> B",
    "agents": [{"path": "...", "input": "...", "output": "..."}]
  }
  ```

- Emit it once per top-level run, just before/after `algo_start` (or
  on first agent invocation if no algorithm wrapper). Coordinate with
  1-2 — that task accepts the new envelope kind on the dashboard side.

### Process-shutdown semantics

The fragile spot is `python process exits`. Options to evaluate:

- `atexit.register(observer.flush_sync)` — works but has caveats
  inside async event loops.
- `asyncio.run(...)`'s default cleanup runs cancel callbacks which
  give a small window to flush.
- A "send-then-confirm" pattern: each event POST returns 200 only
  after registry write; track outstanding ack count.

Pick the simplest one that survives `Ctrl-C` without losing events.
Document your choice in `operad/dashboard.py`'s module docstring.

## Acceptance criteria

1. Re-run `uv run --extra observers python apps/demos/agent_evolution/run.py
   --offline --dashboard --generations 6 --population 8`. After the
   demo's "finished" line:
   - `curl http://localhost:7860/runs/<algo_run_id>/fitness.json` returns
     all 6 generations.
   - The same run's `state` is `"ended"`, not `"running"`.
2. The new `graph_envelope` is accepted (you can verify by handcrafted
   curl POST after 1-2 lands; for now, document the contract).
3. `/runs` no longer has 97 synthetic sub-runs as top-level entries —
   each child Agent event carries `parent_run_id` in metadata. (The
   dashboard-side filtering is 1-2's responsibility; 1-1 just provides
   the data.)
4. Tests under `tests/runtime/test_dashboard_transport.py` (new) cover:
   - Queue drain at process exit.
   - Batch POST round-trip.
   - parent_run_id propagation from algorithm into nested agent calls.

## Dependencies & contracts

### Depends on

- Nothing earlier (this is foundation).

### Exposes for downstream iterations

- Envelope kind `graph_envelope` with the schema above.
- `AgentEvent.metadata.parent_run_id: str | None`.
- The transport drains synchronously on host process exit.

## Risks / non-goals

- Don't change algorithm semantics. The contextvar should be
  read-only for algorithms; only the runtime observer plumbing
  manipulates it.
- Don't add a persistent queue (file-backed) — keep it in-memory.
  Persistence is task 4-4.
- Don't change the OTel observer or the in-process observer; they
  already work. Only the HTTP forwarder is broken.

## Verification checklist

- [ ] Run demo end-to-end; confirm 6 generations land.
- [ ] `pytest tests/runtime/ -k transport` passes.
- [ ] `make test` passes.
- [ ] No new top-level dependencies in `pyproject.toml`.
- [ ] Module docstring in `operad/dashboard.py` documents the
      shutdown-flush guarantee.
