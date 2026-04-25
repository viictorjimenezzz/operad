# 4-4 — Run persistence (SQLite mirror)

> **Iteration**: 4 of 4. **Parallel slot**: 4.
> **Owns**: a NEW SQLite-backed mirror of the runs registry, snapshot
> hooks, and a small "archive browser" page.
> **Forbidden**: in-memory registry semantics (`RunRegistry` class
> shape stays the same), per-algorithm layouts, frontend infra.

## Problem

The runs registry in `apps/dashboard/operad_dashboard/runs.py` is
in-memory and bounded (default 200). When the dashboard restarts —
which happens every `docker compose restart` — all run history
evaporates. For a "local-first dev tool" that's borderline acceptable;
for an "experiment platform" (the direction this revamp aims at),
it's untenable.

A pinned run from yesterday should still be there today. A benchmark
report tagged "baseline-v1" must survive a server upgrade. A cassette
determinism check that succeeded last week should still be referenceable.

## Scope

### Owned files

- New: `apps/dashboard/operad_dashboard/persistence.py` — SQLite store
  with schema migrations.
- `apps/dashboard/operad_dashboard/runs.py` — extend to mirror run
  state to the SQLite store on terminal events (algo_end, error). Keep
  the in-memory model as the hot path.
- `apps/dashboard/operad_dashboard/cli.py` — add a `--data-dir <path>`
  flag (default `./.dashboard-data/`).
- New: `apps/dashboard/operad_dashboard/routes/archive.py` — archived
  runs API (separate from `/runs` which is the live registry).
- New: `apps/frontend/src/dashboard/pages/ArchivePage.tsx`
- New: `apps/frontend/src/dashboard/pages/ArchivedRunPage.tsx`
- `apps/frontend/src/dashboard/routes.tsx` — small textual merge.
- Tests.

### Forbidden files

- Per-algorithm layouts (iter-3).
- `RunInfo` schema changes that would break iter-1-2 and iter-3.
  Persistence should serialize what's already there, not redesign it.

## Direction

### Schema

Two tables minimum:

```
runs (
  run_id TEXT PRIMARY KEY,
  algorithm_path TEXT,
  state TEXT,
  started_at REAL,
  ended_at REAL,
  parent_run_id TEXT,
  synthetic INTEGER,
  summary_json TEXT  -- canonical JSON of RunInfo at end-of-run
)

events (
  run_id TEXT,
  seq INTEGER,
  ts REAL,
  envelope_json TEXT,
  PRIMARY KEY (run_id, seq)
)
```

The events table is high-volume; consider:

- Storing only events for non-synthetic runs by default.
- Compressing envelopes via `gzip` if `len > 4KB`.
- Optional: a per-run "last-N events" cap (configurable via flag).

### Hot-path semantics

- The in-memory `RunRegistry` keeps doing what it does today.
- On terminal events (`algo_end`, error, timeout), snapshot the run to
  SQLite (background task; don't block the request).
- Optional: snapshot every N events for long-running runs so a crash
  doesn't lose the last N-1 events.
- `RunRegistry.get(run_id)` first checks memory, then SQLite if a
  flag is set (default off — keep `/runs` lean, only `/archive` hits
  SQLite).

### Archive API

```
GET /archive
  query: ?from=<ts>&to=<ts>&algorithm=<class>&limit=<n>
  returns: list of archived run summaries

GET /archive/{run_id}
  returns: full run summary + events

DELETE /archive/{run_id}
  returns: {ok: true}

POST /archive/{run_id}/restore
  - copies the run back into the in-memory registry, so it shows up
    in /runs again
```

### Archive page

A separate `/archive` route (sister to `/`) that lets users:

- Browse old runs by date / algorithm.
- Click into one → renders using the same `<DashboardRenderer>` as
  live runs (per-algorithm layouts work the same).
- "Restore to live" copies it back to the in-memory registry (e.g. so
  it shows up in cross-run comparison).

Don't try to deduplicate the archive page with the live runs list —
they have different mental models (live = currently active, archive =
historical).

### Backups

The user should be able to ship the SQLite file elsewhere:

- Default location: `./.dashboard-data/dashboard.sqlite`.
- Dockerfile: declare a volume for `/app/.dashboard-data/` so docker
  compose can persist across restarts.
- A `POST /archive/_export?format=jsonl` returns a streaming JSONL of
  all archived runs (for offline analysis). Optional, add only if
  trivial.

## Acceptance criteria

1. Run a demo, then `docker compose restart operad-dashboard`. The
   run is gone from `/runs` (registry was in-memory) but available
   under `/archive`.
2. Click "Restore to live" → run reappears in `/runs` and is
   comparable in `/experiments`.
3. The dashboard's data dir survives `docker compose down && up`
   (volume).
4. Schema migrations work: starting an old version's data dir with a
   newer dashboard upgrades the schema.
5. Tests cover: snapshot on terminal events, schema migration, archive
   query filters, restore.

## Dependencies & contracts

### Depends on

- 1-2 (registry primitives).
- 4-3 (cassettes can replay into the archive too — coordinate).

### Exposes

- `/archive/*` API.
- A SQLite file at `<data-dir>/dashboard.sqlite` with documented
  schema.
- Stable archived run-id format (same as live).

## Direction notes / SOTA hints

- Use Python's stdlib `sqlite3`. No ORM needed.
- For schema migrations: a small `migrations/` dir with numbered SQL
  files; track applied ones in a `_meta` table.
- For background snapshotting: `asyncio.create_task` from the ingest
  handler. Don't block the request path.
- For the volume: docker compose `volumes:` section in
  `docker-compose.yml`.

## Risks / non-goals

- Don't add cross-run analytics in the archive page; that's
  `/experiments`'s job. Archive is just "where old runs live."
- Don't sync to a remote store (S3 etc.).
- Don't make the SQLite store the primary read path — keep memory
  hot.

## Verification checklist

- [ ] Restart-survives test passes.
- [ ] Volume mount works in docker compose.
- [ ] Archive query filters work.
- [ ] Restore round-trips correctly.
- [ ] Tests pass.
