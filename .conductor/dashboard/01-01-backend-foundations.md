# 01-01 Backend foundations

**Branch**: `dashboard/backend-foundations`
**Wave**: Sequence 1, parallel batch
**Dependencies**: none
**Estimated scope**: medium (backend only)

## Goal

Land every backend delta the rest of the redesign depends on, in one PR,
so frontend agents can wire UI without round-tripping with backend
agents. Five additions, all `GET`-only:

1. New `/api/agent-classes` route (class-level grouping).
2. `/api/manifest` adds `cassettePath`, `cassetteStale`, `tracePath`.
3. `/runs/{id}/agent/{path}/parameters` adds `tape_link` and
   `gradient` per param when applicable.
4. New `/runs/{run_id}/parameter-evolution/{path:path}` aggregated
   endpoint.
5. Verify and harden `metadata.metrics` propagation (already works;
   add a test that catches regressions).

## Why this exists

- §1 of `00-contracts.md` says the agents sidebar is three-level
  (Class → Instance → Invocation). The class-level data must come from
  the backend so the frontend doesn't reinvent grouping.
- §10 reserves the new routes; this brief implements them.
- §15 requires gradient + tape_link metadata; without it the parameter
  drawer's "Why" sub-pane (brief `03-05`) cannot render.

## Files to touch

- `apps/dashboard/operad_dashboard/routes/groups.py` —
  add `list_agent_classes` (`/api/agent-classes`).
- `apps/dashboard/operad_dashboard/agent_routes.py` —
  - extend `agent_parameters` (`groups.py:688-704`) to include
    `tape_link` and `gradient` from event metadata when present;
  - add `parameter_evolution` route below it (new endpoint).
- `apps/dashboard/operad_dashboard/app.py` (or wherever
  `/api/manifest` is implemented) — add cassette fields.
- `apps/dashboard/operad_dashboard/runs.py` —
  - extend `_record_algo` (`runs.py:368-471`) so `gradient_applied`
    events store enough state to be joined back per-parameter;
  - extend `_record_agent` (`runs.py:473-527`) so per-parameter
    snapshots store the iter/epoch context.
- `apps/dashboard/tests/` — add `test_agent_classes.py`,
  extend `test_agent_routes.py` with `parameter_evolution` cases,
  extend `test_manifest.py` with cassette fields.

## Contract reference

See `00-contracts.md` §1 (identity), §8 (parameter evolution data
model), §10 (backend routes), §15 (data emission requirements).

## Implementation steps

### Step 1 — `/api/agent-classes`

Bucket the existing `/api/agents` payload by `class_name`:

```python
@router.get("/api/agent-classes")
async def list_agent_classes(request: Request) -> JSONResponse:
    """Return one entry per agent class. Each entry contains its instances."""
    runs = _all_runs(request)
    by_class: dict[str, dict[str, Any]] = {}
    for info in runs:
        if info.is_algorithm and not _is_trainer(info):
            continue
        if info.synthetic:
            continue
        cls = _agent_class_name(info) or "Agent"
        bucket = by_class.setdefault(cls, {
            "class_name": cls,
            "root_agent_path": info.root_agent_path,
            "instance_count": 0,
            "running": 0,
            "errors": 0,
            "first_seen": float("inf"),
            "last_seen": 0.0,
            "instances": {},   # hash_content -> AgentGroupSummary
        })
        # ... aggregate (see /api/agents for the pattern)
    # Convert instances dict to list, return.
```

The shape mirrors `/api/agents` for individual instances inside the
returned class entry. Reuse the helpers already in
`groups.py` (`_latest_root_hash_content`, `_class_name_from_path`).

### Step 2 — Manifest cassette fields

`/api/manifest` currently returns `{mode, version, langfuseUrl,
allowExperiment, cassetteMode}`. Add:

- `cassettePath: str | null` — value of `OPERAD_CASSETTE_PATH` env var
  if set, else None.
- `cassetteStale: bool` — heuristic: any file under `operad/**/*.py`
  newer than the cassette mtime. Use the same logic as
  `make cassettes-check` (see existing implementation in
  `operad/runtime/cassette/checker.py` if present, else implement
  inline using `pathlib.Path.glob` and `os.path.getmtime`).
- `tracePath: str | null` — `os.environ.get("OPERAD_TRACE")`.

### Step 3 — `parameters` route enrichment

Currently `agent_parameters` returns `{agent_path, parameters: [...]}`
where each entry is `{requires_grad, path, value, hash}` (read from
`metadata.parameters`). Extend each entry with:

```python
{
  "requires_grad": ...,
  "path": ...,
  "value": ...,
  "hash": ...,
  "tape_link": {                    # null when not produced by an optimizer step
    "epoch": int, "batch": int, "iter": int, "optimizer_step": int
  } | null,
  "gradient": {                     # null when no gradient observed
    "message": str, "severity": "low" | "medium" | "high",
    "target_paths": [str, ...]
  } | null
}
```

Source: walk `info.events` for the most recent `algo_event` of kind
`gradient_applied` whose `target_paths` includes `path`, before the
event that produced `metadata.parameters`. The Trainer brief
(`05-05`) will make sure `gradient_applied` events carry these fields.

### Step 4 — `/runs/{run_id}/parameter-evolution/{path:path}`

Returns the historical timeline of one parameter:

```python
{
  "path": "research_analyst.stage_0.role",
  "type": "text" | "rule_list" | "example_list" | "float" | "categorical" | "configuration",
  "points": [
    {
      "run_id": str,
      "started_at": float,
      "value": Any,
      "hash": str,
      "gradient": { ... } | null,
      "source_tape_step": { ... } | null,
      "langfuse_url": str | null,
      "metric_snapshot": { "train_loss": 0.71, ... } | null
    },
    ...
  ]
}
```

Implementation:

- Walk `RunRegistry.runs_by_hash_full(hash_content_of_root)` (need to
  resolve from the run_id first).
- For each run, pull the latest `parameter_snapshot` for `path` from
  `RunInfo.parameter_snapshots`.
- Join with `gradient_applied` events by `optimizer_step` /
  `target_paths`.
- Infer `type` from the value (string → text; list of str → rule_list;
  list of dict → example_list; number → float; configuration dict →
  configuration; otherwise categorical).

### Step 5 — Emit-site verification

Run examples 01-04 with the dashboard attached and assert that:
- `metadata.parameters` contains `requires_grad` for every parameter
  (already true).
- `gradient_applied` events appear during examples 03 (Trainer) and 04
  (EvoGradient).

If they do not, file a follow-up issue under `operad/optim/` or
`operad/train/` and have your brief reference it. Do not paper over
the gap in the dashboard.

## Design alternatives

1. **Compute `cassetteStale` lazily on every `/api/manifest` call.**
   Recommendation: yes, it's cheap (≤ a few hundred file stats) and
   correctness > cycle count.
2. **Aggregate `parameter-evolution` on demand vs precompute on
   ingest.** Recommendation: aggregate on demand. Per-run state is
   already stored; precomputing creates a second source of truth.

## Acceptance criteria

- [ ] `GET /api/agent-classes` returns the expected shape and groups
  the demo runs (examples 01-04) under the correct class names.
- [ ] `GET /api/manifest` includes `cassettePath`, `cassetteStale`,
  `tracePath`. Manual: with `OPERAD_CASSETTE_PATH=foo`, the field
  reflects `foo`.
- [ ] `GET /runs/{id}/agent/{path}/parameters` includes `tape_link`
  and `gradient` keys (null when not applicable, populated otherwise).
- [ ] `GET /runs/{id}/parameter-evolution/{path}` returns the timeline
  for a known trainable parameter on example 03.
- [ ] No existing route's response shape regressed. Add a snapshot
  test if helpful.
- [ ] `uv run pytest apps/dashboard/tests/ -v` passes.

## Test plan

- `apps/dashboard/tests/test_agent_classes.py` — fixture: 2 instances
  of `class_a`, 1 of `class_b`. Assert grouping is correct.
- `apps/dashboard/tests/test_agent_routes.py` — add cases for the
  enriched `parameters` route and the new `parameter-evolution` route.
- `apps/dashboard/tests/test_manifest.py` — assert cassette fields.

## Out of scope

- Frontend reads of any of these fields. (That's brief 01-03 / 03-05.)
- Backend changes to `operad/` core; only flag emit-site gaps.
- Authentication / persistence.

## Stretch goals

- Add `event_count` to `/api/agent-classes` per class.
- Add a `last_invocation` short-summary per class that the new
  `AgentsByClassPage` (brief `01-03`) can render without a second
  round-trip.
- Cache `parameter-evolution` per `(run_id, path, last_event_at)`
  tuple to avoid recomputation on rapid polling.
