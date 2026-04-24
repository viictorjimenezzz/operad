# 2-3 — Dashboard PromptDrift timeline

**Wave.** 2. **Parallel with.** 2-{1,2,4,5}.

## Context

`PromptDrift` (a Trainer callback) already warns when an agent's
`hash_content` changes significantly across epochs. What's missing
is a visual history: a timeline of hash changes per parameter, so a
user can *see* prompt evolution as the trainer runs.

## Scope — in

### `operad/train/callbacks.py`

Extend `PromptDrift` to *emit* (not just log) an `AlgorithmEvent`:

```python
AlgorithmEvent(
    run_id=...,
    algorithm_path="PromptDrift",
    kind="iteration",                # reuse existing kind
    payload={
        "epoch": int,
        "hash_before": str,          # 16-hex
        "hash_after": str,
        "changed_params": list[str], # dotted paths of changed params
        "delta_count": int,          # how many params changed
    },
    ...
)
```

Emit once per epoch (or every `emit_every` epochs, default 1).

### `apps/dashboard/operad_dashboard/routes/drift.py` (new)

- `GET /runs/{run_id}/drift.json` — time-ordered list of
  `PromptDrift` events.
- `GET /runs/{run_id}/drift.sse` — live feed.

### `apps/dashboard/operad_dashboard/templates/partials/_drift.html` (new)

- A vertical timeline. Each entry shows:
  - epoch index,
  - `hash_before[:8] → hash_after[:8]` in monospace,
  - changed param paths (bullets, collapsed by default, click to
    expand).
- Use pure HTML + CSS; no chart library needed.

### `apps/dashboard/operad_dashboard/static/js/drift.js` (new)

- EventSource → prepend new entries to the timeline.

### Tests

`tests/train/test_prompt_drift_events.py`:

- Running a `Trainer.fit` with `PromptDrift` registered produces one
  `iteration` event per epoch with the new payload shape.
- `hash_before` / `hash_after` are 16-hex strings.
- `changed_params` lists only the dotted paths whose parameter value
  actually changed.

`apps/dashboard/tests/test_drift.py`:

- Endpoint returns `drift.json` with correct shape.
- Panel hides when no `PromptDrift` events exist.

## Scope — out

- Do not attempt to diff the actual textual content of changed
  parameters in the panel. Showing changed paths + hash delta is
  enough; users can click through to `PromptTraceback` for
  content-level diffs.
- Do not persist drift history across dashboard restarts. In-memory
  only, same as the rest of the dashboard.

## Dependencies

- `operad/train/callbacks.py` `PromptDrift` (existing).
- `operad.runtime.events` (existing).

## Design notes

- **algorithm_path="PromptDrift"** keeps it separable from the agent
  tree — it's a *meta* algorithm running alongside the trainer.
- **Payload shape** reuses the existing `iteration` kind; no schema
  change.
- **Panel positioning.** Place below fitness + mutations on the
  run-detail page. Height: auto, capped with `max-height: 240px;
  overflow-y: auto`.

## Success criteria

- `pytest tests/train/test_prompt_drift_events.py
  apps/dashboard/tests/test_drift.py` passes.
- During a 3-epoch `Trainer.fit`, the drift panel shows 3 timeline
  entries as epochs complete.
- Existing `PromptDrift` warning log output is unchanged (the event
  emission is additive).
