# 4-3 — Cassette inspector

> **Iteration**: 4 of 4. **Parallel slot**: 3.
> **Owns**: a NEW `/cassettes` route, page, replay UI, and a backend
> endpoint that lists/replays cassettes.
> **Forbidden**: existing layouts/components, runs registry, training
> pipelines.

## Problem

operad's cassette system records LLM call responses (and, since stream
5-2, training-step states) so tests and demos can replay deterministically
offline. Cassettes live as `.jsonl` files; training cassettes as
`.train.jsonl`. They're a load-bearing piece of the framework's
"determinism story" but completely invisible to dashboard users today.

A cassette inspector should:

- List all cassettes the dashboard process can find.
- Replay a cassette → show the resulting events as if it were a live
  run.
- Validate determinism: replay twice, assert byte-equal output.

This is the dashboard's "show me the framework's reproducibility"
surface.

## Scope

### Owned files

- New: `apps/dashboard/operad_dashboard/routes/cassettes.py` — list /
  replay / determinism-check endpoints.
- New: `apps/dashboard/operad_dashboard/cassette_replay.py` — small
  helper that reads a cassette and re-emits events through the
  dashboard's `/_ingest` (so the cassette appears as a normal run).
- New: `apps/frontend/src/dashboard/pages/CassettesPage.tsx`
- New: `apps/frontend/src/dashboard/pages/CassetteDetailPage.tsx`
- New: `apps/frontend/src/shared/panels/cassette-list.tsx`
- New: `apps/frontend/src/shared/panels/replay-controls.tsx`
- `apps/frontend/src/dashboard/routes.tsx` — register routes (small
  textual merge with 4-1 / 4-2).
- Tests.

### Forbidden files

- Existing layouts/components.
- `operad/utils/cassette.py` — read it, but don't modify.

## Direction

### Discover cassettes

Operad's cassette context manager (`operad/utils/cassette.py`) reads
from a configured path. Cassette files exist under:

- Test fixtures: `tests/cassettes_feat/cassettes/`.
- Sample traces: `tests/fixtures/`.
- User-recorded cassettes: wherever they put them — typically the
  user passes a path explicitly to `cassette_context()`.

For the dashboard, accept a configurable directory:

- `OPERAD_DASHBOARD_CASSETTE_DIR` env var, default `./.cassettes/`.
- The dashboard recursively lists `*.jsonl` and `*.train.jsonl` files.
- For each, parse a small header — first line — to extract metadata
  (algorithm, run_id, recorded_at). If the cassette format doesn't
  carry that today, document the gap and fall back to file path /
  mtime.

### Backend API

```
GET  /cassettes
  returns: [{path, type, size, mtime, metadata}]

POST /cassettes/replay
  body: {path: str, run_id_override?: str}
  returns: {run_id: str}
  side effect: emits events through /_ingest as if the cassette were
               running live (rate-limited or instant — your call)

POST /cassettes/determinism-check
  body: {path: str}
  returns: {ok: bool, diff: [{event_index, field, expected, actual}]}
```

### Replay implementation

`cassette_replay.py` reads the cassette, then for each recorded event,
POSTs an envelope to the local `/_ingest`. The dashboard then displays
it as a normal run (overview, evolution, debate, whatever — the
algorithm's layout takes over).

Decide whether replay is real-time (one event per second) or
fast-forwarded (all events in a burst). **Recommend fast-forwarded**
with a small per-event delay (e.g. 50ms) to give SSE subscribers time
to render. Make it configurable via a query param.

### Determinism check

Two replays of the same cassette into a fresh `RunInfo` must produce
byte-equal results. Implement:

1. Replay cassette into a temporary in-memory `RunInfo`.
2. Replay again into another fresh `RunInfo`.
3. Diff their canonical-JSON serializations.

Surface the diff in the UI as a green badge ("byte-equal ✓") or a
red expandable list of differences.

### Page IA

```
/cassettes
  ┌─────────────────────────────────────────────┐
  │ ALL CASSETTES (12)        [Refresh] [Path] │
  │  evolutionary_run_001.jsonl   12 KB   5d ago│
  │    [▶ Replay] [✓ Det check]                 │
  │  trainer_drift_v2.train.jsonl 8 KB   2h ago │
  │    [▶ Replay] [✓ Det check]                 │
  │  ...                                        │
  └─────────────────────────────────────────────┘

/cassettes/<path>
  ┌─────────────────────────────────────────────┐
  │ Cassette: evolutionary_run_001.jsonl        │
  │  - 6 generations, 96 inner agent calls      │
  │  - recorded against EvoGradient             │
  │  - last replay: 12s ago, byte-equal ✓        │
  │  [▶ Replay] [✓ Determinism check]           │
  ├─────────────────────────────────────────────┤
  │  Recorded events preview (first 100):       │
  │    [JSON viewer, paginated]                 │
  └─────────────────────────────────────────────┘
```

## Acceptance criteria

1. Place a recorded cassette in `./.cassettes/` (or configure the env
   var). Visit `/cassettes` → see it listed.
2. Click "Replay" → a new run appears in the runs list with the
   replayed events; navigate into it → see the algorithm's normal
   layout populated.
3. Click "Determinism check" → see the result. If you intentionally
   tamper with the cassette (e.g. flip one byte), the check should
   fail with a clear diff.
4. Tests cover: cassette discovery, replay → ingest path, determinism
   pass and fail cases.

## Dependencies & contracts

### Depends on

- 1-1, 1-2 (transport + registry).
- `operad/utils/cassette.py` for parsing.

### Exposes

- `/cassettes/*` API.
- A `CassetteList` and `CassetteDetail` page.

## Direction notes / SOTA hints

- For the determinism diff, `deepdiff` is overkill. A simple
  per-event JSON-canonical hash + index-aligned compare is enough.
- Cassette files can be large; stream-parse line-by-line, don't load
  the whole file into memory.
- For the JSON preview in the detail page, virtualize if >100
  events.

## Risks / non-goals

- Don't add cassette recording from the UI — recording requires a live
  backend and is well-served by the existing `make cassettes-refresh`
  CLI.
- Don't add cassette editing.
- Don't auto-replay all cassettes on dashboard startup.

## Verification checklist

- [ ] Demo: existing cassette from the repo's tests dir lists, replays,
      and passes determinism check.
- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Tampered cassette fails determinism check with sensible diff.
