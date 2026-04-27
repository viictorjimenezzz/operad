# 14 — Backend deltas

**Stage:** 3 (parallel; no frontend deps)
**Branch:** `dashboard-redesign/14-backend-deltas`
**Subagent group:** E (Backend)

## Goal

Land all backend additions the redesign needs, in one place, while the
frontend subagents work in parallel. Most are small projections over
the existing `RunRegistry`; two are payload extensions in
`operad/algorithms/` (TalkerReasoner, AutoResearcher); one is a new
emit path on `OPROOptimizer` (Q7); one is the persistence of
`PromptTraceback`. None require touching `operad/core/` agent
internals.

## Read first

- `00-CONTRACTS.md` §4 (route contracts), §5 (algorithm payload
  extensions).
- `apps/dashboard/operad_dashboard/runs.py` — `RunInfo`, `RunRegistry`.
- `apps/dashboard/operad_dashboard/observer.py` — `serialize_event`
  (the seam where `metadata.metrics` propagates).
- `apps/dashboard/operad_dashboard/persistence.py` — SQLite archive
  store (notes go here).
- `apps/dashboard/operad_dashboard/agent_routes.py` — existing
  per-agent routes (we extend).
- `apps/dashboard/operad_dashboard/routes/groups.py` — existing
  `/api/agents`, `/api/algorithms`, `/api/trainings`.
- `operad/algorithms/talker_reasoner.py:441-452` — `algo_start` emit
  site.
- `operad/algorithms/autoresearch.py:140-189` — `iteration` emit sites
  + `_one_attempt` body.
- `operad/optim/optimizers/opro.py` — currently emits nothing.
- `operad/train/trainer.py:648-714` — `gradient_applied` emit.
- `operad/optim/backprop/traceback.py` — `PromptTraceback` artifact.
- `INVENTORY.md` §13 (observers), §22 (PromptTraceback).

## Files to touch

Backend (`apps/dashboard/operad_dashboard/`):

- `routes/groups.py` — add `/api/agents/:hash/metrics`,
  `/api/agents/:hash/parameters`.
- `routes/__init__.py` — register the new routes.
- `runs.py` — extend `RunInfo` to track `metrics: dict[str, float]`,
  `notes_markdown: str`, `parameter_snapshots: list[dict]`,
  `traceback_path: str | None`.
- `runs.py` — add a `runs_by_hash_full(hash)` helper that returns
  *every* run sharing the hash (for the metrics endpoint).
- `runs.py` — extend `RunInfo.summary()` to include the new fields.
- `observer.py` — propagate `metadata.metrics` from envelope to
  `RunInfo.metrics`.
- `app.py` — add `PATCH /api/runs/:run_id/notes` (Markdown notes).
- `persistence.py` — add a `notes_markdown` column to the runs table
  (migration).
- `migrations/` — add a new migration file.

`operad/`:

- `operad/algorithms/talker_reasoner.py` — extend `algo_start.payload`
  with the serialized tree (per `00-CONTRACTS.md` §5.1).
- `operad/algorithms/autoresearch.py` — add `attempt_index` to every
  iteration emit; emit the new `"plan"` event after the planner runs
  (per `00-CONTRACTS.md` §5.2).
- `operad/algorithms/beam.py` — extend the per-candidate event
  metadata with the synthetic-child role (`"generator"` or `"critic"`)
  so the frontend can deep-link without guessing (Brief 06 dependency).
- `operad/optim/optimizers/opro.py` — implement event emission. Pin a
  per-instance `_algo_run_id` mirroring `EvoGradient.session()`. Emit
  `algo_start`, `iteration phase="propose"`, `iteration
  phase="evaluate"`, `algo_end` (per `00-CONTRACTS.md` §5.3).
- `operad/train/trainer.py` — persist `PromptTraceback.to_jsonl()` to a
  per-run directory and reference the path in the trainer's
  `RunInfo.traceback_path` via a small metadata-passthrough call.

## Endpoint specifications

### `GET /api/agents/:hash/metrics`

```python
@router.get("/api/agents/{hash_content}/metrics")
async def agent_group_metrics(hash_content: str) -> JSONResponse:
    """Per-invocation metric series for the group sharing this hash."""
    runs = registry.runs_by_hash_full(hash_content)  # ordered by started_at asc
    metrics: dict[str, dict] = {}
    for run in runs:
        # Built-in metrics
        for name, getter in BUILTIN_METRICS.items():
            metrics.setdefault(name, {"unit": UNITS[name], "series": []})
            metrics[name]["series"].append({
                "run_id": run.run_id,
                "started_at": run.started_at,
                "value": getter(run),  # may be None
            })
        # User-supplied metrics from envelope.metadata.metrics
        for name, value in (run.metrics or {}).items():
            metrics.setdefault(name, {"unit": None, "series": []})
            metrics[name]["series"].append({
                "run_id": run.run_id,
                "started_at": run.started_at,
                "value": value,
            })
    return JSONResponse({"hash_content": hash_content, "metrics": metrics})
```

`BUILTIN_METRICS` covers `latency_ms`, `prompt_tokens`,
`completion_tokens`, `cost_usd`. `UNITS` maps to `"ms"`, `"tokens"`,
`"tokens"`, `"usd"`.

### `GET /api/agents/:hash/parameters`

```python
@router.get("/api/agents/{hash_content}/parameters")
async def agent_group_parameters(hash_content: str) -> JSONResponse:
    runs = registry.runs_by_hash_full(hash_content)
    paths: set[str] = set()
    series: list[dict] = []
    for run in runs:
        snapshot = run.latest_parameter_snapshot()  # walks events for this run
        if not snapshot:
            continue
        paths.update(snapshot.keys())
        series.append({
            "run_id": run.run_id,
            "started_at": run.started_at,
            "values": {p: {"value": v, "hash": _short_hash(repr(v))}
                       for p, v in snapshot.items()},
        })
    return JSONResponse({
        "hash_content": hash_content,
        "paths": sorted(paths),
        "series": series,
    })
```

`latest_parameter_snapshot()` reads the most recent
`iteration phase="epoch_end"` payload's `parameter_snapshot` dict (set
by `Trainer`) OR walks each terminal `agent_event.metadata.parameters`
(set by `Agent._invoke_envelope`). Either source is fine; the helper
prefers epoch_end snapshots when present.

### `PATCH /api/runs/:run_id/notes`

```python
@app.patch("/api/runs/{run_id}/notes")
async def update_notes(request: Request, run_id: str) -> JSONResponse:
    body = await request.json()
    markdown = str(body.get("markdown") or "")
    obs = request.app.state.observer
    info = obs.registry.get(run_id)
    if info is not None:
        info.notes_markdown = markdown
    archive = request.app.state.archive_store
    if archive is not None:
        archive.set_notes(run_id, markdown)
    return JSONResponse({"run_id": run_id,
                         "notes_markdown": markdown,
                         "updated_at": time.time()})
```

`archive.set_notes(run_id, markdown)` is implemented in
`persistence.py` after the migration. The dashboard's runtime registry
also keeps a `notes_markdown` field so the next `summary()` returns it.

### Existing `GET /runs/:id/summary` extensions

Already covered by extending `RunInfo.summary()` to include the new
fields. No new route — additive only.

## Algorithm payload extensions

### TalkerReasoner — `algo_start` adds `tree`

In `operad/algorithms/talker_reasoner.py:441-452`, replace the existing
emit with one that includes the serialized tree:

```python
emit_algorithm_event(
    AlgorithmEvent(
        run_id=_RUN_ID.get(),
        algorithm_path=type(self).__name__,
        kind="algo_start",
        payload={
            "process": tree.name,
            "purpose": tree.purpose,
            "start_node_id": self._current_id,
            "max_turns": self.max_turns,
            "scripted_messages": …,
            "tree": _serialize_tree(tree),
        },
        started_at=time.time(),
        finished_at=None,
        metadata={},
    )
)
```

Helper `_serialize_tree(tree)`:

```python
def _serialize_tree(tree: ScenarioTree) -> dict:
    nodes = []
    def walk(node, parent_id):
        nodes.append({
            "id": node.id,
            "title": node.title,
            "prompt": node.prompt,
            "terminal": node.terminal,
            "parent_id": parent_id,
        })
        for c in node.children or []:
            walk(c, node.id)
    walk(tree.root, None)
    return {
        "name": tree.name,
        "purpose": tree.purpose,
        "rootId": tree.root.id,
        "nodes": nodes,
    }
```

### AutoResearcher — attempt_index + plan

In `operad/algorithms/autoresearch.py`:

- Pass `attempt_index` from `run()` to `_one_attempt()` (currently
  not threaded). Add `attempt_index: int` keyword.
- Inside `_one_attempt`, every iteration emit gains
  `payload["attempt_index"] = attempt_index`.
- After the planner produces `ResearchPlan`, emit:

```python
emit_algorithm_event(AlgorithmEvent(
    run_id=_RUN_ID.get(),
    algorithm_path="AutoResearcher",
    kind="plan",  # extend AlgoKind to include this
    payload={"attempt_index": attempt_index, "plan": plan.model_dump()},
    started_at=time.time(),
    finished_at=time.time(),
    metadata={},
))
```

`AlgoKind` in `operad/runtime/events.py` must include `"plan"` (and,
for completeness, `"gradient_applied"` which Trainer already emits but
isn't in the literal). Update the type:

```python
AlgoKind = Literal[
    "algo_start", "algo_end", "algo_error",
    "generation", "round", "cell", "candidate",
    "iteration", "batch_start", "batch_end",
    "gradient_applied",   # already emitted by Trainer
    "plan",                # new (AutoResearcher)
    "propose", "evaluate", # used? See OPRO note below; emit as
                            # iteration with phase fields, not new kinds.
]
```

OPRO emits `iteration` with `phase` set to `"propose"` / `"evaluate"`,
so we do NOT add new kinds for OPRO.

### Beam — synthetic-child role

In `operad/algorithms/beam.py`, when invoking the generator and the
critic, ensure the inner agent's `OperadOutput.metadata` is augmented
with a hint:

```python
out = await gen.invoke(x, _operad_meta={"role": "beam_generator", "candidate_index": i})
```

If the existing `Agent.invoke()` doesn't accept `_operad_meta`, plumb
it through `_metadata_kwargs` in `agent.py` (the simplest non-invasive
path). Alternative: emit a small `algo_emit` event tagging the
candidate-to-runId mapping. Discuss with the parent agent before
choosing.

### OPRO — emit lifecycle (Q7)

In `operad/optim/optimizers/opro.py`, refactor to expose a `session()`
async context manager mirroring `EvoGradient.session()`:

```python
class OPROOptimizer:
    def __init__(self, ...):
        ...
        self._algo_run_id: str | None = None

    @asynccontextmanager
    async def session(self):
        # If we're inside a Trainer's _enter_algorithm_run, emit as a
        # nested algorithm run (parent_run_id set automatically).
        with _enter_algorithm_run(reuse_existing=False) as run_id:
            self._algo_run_id = run_id
            emit_algorithm_event(AlgorithmEvent(
                run_id=run_id, algorithm_path="OPRO", kind="algo_start",
                payload={"params": [str(p) for p in self.params],
                         "history_window": self.history_window,
                         "max_retries": self.max_retries},
                started_at=time.time(), finished_at=None, metadata={},
            ))
            try:
                yield self
                emit_algorithm_event(AlgorithmEvent(
                    run_id=run_id, algorithm_path="OPRO", kind="algo_end",
                    payload={"steps": self._step_index,
                             "best_score": self._best_score,
                             "final_values": {p.path: str(p.value) for p in self.params}},
                    started_at=time.time(), finished_at=time.time(), metadata={},
                ))
            except Exception as e:
                emit_algorithm_event(AlgorithmEvent(
                    run_id=run_id, algorithm_path="OPRO", kind="algo_error",
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=time.time(), finished_at=time.time(), metadata={},
                ))
                raise
            finally:
                self._algo_run_id = None
```

Inside `step()`, wrap `_apply_param_update` with two emits per
candidate attempt:

```python
async def _apply_param_update(self, param):
    self._step_index += 1
    proposal = await self.opro_agent(...)  # the LLM proposer call
    candidate_text = proposal.new_value
    emit_algorithm_event(AlgorithmEvent(
        run_id=self._algo_run_id, algorithm_path="OPRO", kind="iteration",
        payload={"iter_index": self._step_index, "step_index": self._step_index,
                 "phase": "propose", "param_path": param.path,
                 "candidate_value": candidate_text,
                 "history_size": len(history)},
        started_at=time.time(), finished_at=None, metadata={},
    ))
    score = await self.evaluator(param, candidate_text)
    accepted = score > best_so_far
    emit_algorithm_event(AlgorithmEvent(
        run_id=self._algo_run_id, algorithm_path="OPRO", kind="iteration",
        payload={"iter_index": self._step_index, "step_index": self._step_index,
                 "phase": "evaluate", "param_path": param.path,
                 "candidate_value": candidate_text, "score": score,
                 "accepted": accepted},
        started_at=time.time(), finished_at=time.time(), metadata={},
    ))
    if accepted:
        param.write(candidate_text)
        self._best_score = score
```

Trainer is already calling `optimizer.step()`; users who want the OPRO
view either (a) call `async with optimizer.session(): await optimizer.step()` directly,
or (b) the Trainer is updated to enter OPRO's session if the optimizer
defines one. Cleanest: make `Trainer._fit_loop` call
`await stack.enter_async_context(optimizer.session())` if the
optimizer has a `session()` attribute. Discuss in the PR.

## PromptTraceback persistence

In `operad/train/trainer.py`, after each `gradient_applied`, optionally
write a sibling NDJSON file:

```python
if hasattr(self, "_prompt_tb_dir") and self._prompt_tb_dir:
    tb = PromptTraceback.from_run(self._tape, self._loss)
    path = self._prompt_tb_dir / f"epoch_{epoch}_batch_{batch}.ndjson"
    tb.save(path)
    emit_algorithm_event(AlgorithmEvent(
        run_id=…, algorithm_path="Trainer", kind="iteration",
        payload={"iter_index": epoch, "phase": "traceback",
                 "epoch": epoch, "batch": batch, "path": str(path)},
        ...
    ))
```

`_prompt_tb_dir` is set by a new Trainer arg `traceback_dir: Path | None`.
The dashboard reads these via a new endpoint:

```
GET /runs/:run_id/traceback?epoch=<n>&batch=<m>
  → NDJSON content streamed back
```

The Traceback tab (Brief 13) consumes this. When `traceback_dir` is
unset, `summary.has_traceback = False` and Brief 13's tab is hidden.

## Migration

`apps/dashboard/operad_dashboard/migrations/004_notes_markdown.py`:

```python
def upgrade(conn):
    conn.execute("""
        ALTER TABLE runs ADD COLUMN notes_markdown TEXT NOT NULL DEFAULT ''
    """)
```

Increment migration version. Existing tests will likely need a fresh
DB; document in PR.

## Tests

- `tests/runtime/test_observer_*.py` — verify `metrics` field
  propagates from `OperadOutput.metadata` to the dashboard envelope.
- `apps/dashboard/tests/test_metrics_endpoint.py` — covers
  `/api/agents/:hash/metrics` happy path + empty path.
- `apps/dashboard/tests/test_parameters_endpoint.py`.
- `apps/dashboard/tests/test_notes_patch.py`.
- `tests/algorithms/test_talker_reasoner_payload.py` — assert
  `algo_start.payload` carries `tree` with the right node count.
- `tests/algorithms/test_autoresearcher_payload.py` — assert
  `attempt_index` is present and `plan` event fires.
- `tests/optimizers/test_opro_emit.py` — assert OPRO emits
  start/iteration/end events under a session.
- `tests/train/test_traceback_persistence.py` — assert traceback
  artifacts are written when `traceback_dir` is set.

## Acceptance criteria

- [ ] `GET /api/agents/:hash/metrics` returns the contracted shape and
  works against a 4-run fixture group.
- [ ] `GET /api/agents/:hash/parameters` returns trainable parameter
  evolution.
- [ ] `PATCH /api/runs/:id/notes` persists Markdown to SQLite and is
  reflected in the next `summary()`.
- [ ] `RunInfo.metrics` is populated from envelope `metadata.metrics`.
- [ ] TalkerReasoner `algo_start` carries `tree`.
- [ ] AutoResearcher iterations carry `attempt_index`; new `plan`
  events fire.
- [ ] Beam candidate events identify generator vs critic synthetic
  children.
- [ ] OPRO emits `algo_start`, `iteration phase∈{propose,evaluate}`,
  `algo_end`. OPRO runs appear under `/api/algorithms`.
- [ ] PromptTraceback artifacts are persisted when `traceback_dir` is
  set; `summary.has_traceback` is `True` in that case.
- [ ] All new tests green; existing tests still pass:
  ```
  uv run pytest apps/dashboard/tests/ -v
  uv run pytest tests/ -q
  ```
- [ ] `uv run python -c "import operad"` succeeds (per repo AGENTS.md
  §6).

## Out of scope

- Frontend consumption (Briefs 03, 04, 09, 12, 13, 16 own that).
- New runs/algorithms in operad core.
- Studio integration (Brief 13's badge calls existing endpoints).

## Hand-off

PR body must include:
1. Migration safety notes (existing dashboards reload without errors).
2. A diff hunks summary for each algorithm payload extension.
3. The OPRO session decision (was `Trainer._fit_loop` updated to call
   `optimizer.session()` if present, or did the user have to do it
   manually?).
4. New tests passing locally with cassette replay (the replay path
   must still pass after the algorithm payload extensions; if any
   cassette breaks, regenerate via `make cassettes-refresh`).
