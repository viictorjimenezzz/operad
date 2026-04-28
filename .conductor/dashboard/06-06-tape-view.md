# 06-06 Tape view (Trainer "developer mode")

**Branch**: `dashboard/tape-view`
**Wave**: Sequence 6, parallel batch
**Dependencies**: `01-01` (manifest, parameter-evolution), `05-05`
(Trainer layout)
**Estimated scope**: medium

## Goal

Add a "Tape" toggle on the Trainer's Loss tab (or a dedicated
Trainer "Tape" tab if Loss is too crowded) that renders a
virtualized table of `TapeEntry` records — one row per agent
invocation captured inside `tape()`. This is operad's `gdb` for
training: nobody else exposes per-invocation introspection at this
level.

## Why this exists

§21 of the inventory: `tape()` records every agent invocation; today
the dashboard surfaces aggregate effects (loss curves, parameter
snapshots) but not the underlying tape entries. Without this view,
debugging a bad batch requires `pdb`.

## Files to touch

- New: `apps/frontend/src/components/algorithms/trainer/tape-view.tsx`.
- New: `apps/frontend/src/components/algorithms/trainer/tape-view.test.tsx`.
- New backend route:
  `apps/dashboard/operad_dashboard/routes/tape.py` —
  `GET /runs/{run_id}/tape.json` (returns tape entries from the
  `RunInfo` if recorded; 404 otherwise).
- `apps/dashboard/operad_dashboard/runs.py` — extend `RunInfo` to
  store tape entries when `metadata.tape_entry` is present on
  agent_event.
- `apps/dashboard/operad_dashboard/app.py` — register route.
- `apps/frontend/src/layouts/trainer.json` — add a "Tape" tab.

## Contract reference

`00-contracts.md` §15 (data emission), §13 (folders).

## Implementation steps

### Step 1 — Backend tape capture

In `runs.py` `_record_agent`, when
`metadata.tape_entry` is a dict (the operad core can emit this on
each agent invocation inside `tape()`), append it to a new
`RunInfo.tape_entries: list[dict]` field.

If the operad core does not currently emit `tape_entry`: file a
follow-up issue under `operad/optim/` to add it; then this brief
becomes a stub that renders "tape capture not enabled" until the
emit lands. Surface the gap in the PR body.

### Step 2 — Route

```python
@router.get("/runs/{run_id}/tape.json")
async def get_tape(request: Request, run_id: str) -> JSONResponse:
    info = request.app.state.observer.registry.get(run_id)
    if info is None:
        return _not_found("unknown run_id")
    return JSONResponse({"entries": list(info.tape_entries)})
```

### Step 3 — Component

A virtualized `RunTable` (using `@tanstack/react-virtual`) with
columns:

```
agent_path · input_hash · output_hash · latency · in_tape_for_step ·
gradient_severity · langfuse →
```

Use `kind:"hash"` for hashes, `kind:"score"` for severity. Click a
row → opens the parameter drawer scoped to the parameter affected by
that tape entry, with the corresponding step pre-selected.

### Step 4 — Layout entry

Add to `trainer.json`:

```json
{ "id": "tape", "label": "Tape" }
```

with element:

```json
"tape": { "type": "TrainerTapeView", "props": { "runId": "$context.runId" } }
```

Register in `dashboard-renderer.tsx`.

## Design alternatives

1. **Tape as a separate tab vs a toggle inside Loss.**
   Recommendation: separate tab. Loss is for at-a-glance training
   health; Tape is forensic.
2. **Render full tape inline vs link to a per-tape-entry detail
   view.** Recommendation: inline + click-to-drawer. Avoid yet
   another navigation layer.

## Acceptance criteria

- [ ] When the Trainer run has tape entries, the Tape tab renders a
  virtualized table.
- [ ] Click a row → opens the parameter drawer with the right
  `?param` and `?step`.
- [ ] No tape captured → empty state with the specific shape:
  "tape capture is not enabled for this run; wrap `Trainer.fit`
  inside `async with operad.optim.backprop.tape():`".
- [ ] `pnpm test --run` passes; backend route test passes.

## Test plan

- `tape-view.test.tsx`: 50-entry fixture; assert virtualization
  (limited rendered rows); click row → drawer URL state changes.
- `apps/dashboard/tests/test_tape.py`: 404 when no tape; 200 with
  entries.

## Stretch goals

- Step-debugger UX: ◀ ▶ buttons in the Tape tab move through entries
  one at a time, syncing the drawer + Loss curve cursor.
- Filter by `agent_path` (multi-select chip).
- Export tape as JSONL (clipboard-only).
