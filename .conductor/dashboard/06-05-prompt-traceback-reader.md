# 06-05 PromptTraceback reader

**Branch**: `dashboard/prompt-traceback-reader`
**Wave**: Sequence 6, parallel batch
**Dependencies**: `01-01` (manifest), `05-05` (Trainer Traceback tab)
**Estimated scope**: medium

## Goal

Build the `PromptTracebackReader` component that loads and renders
an NDJSON `PromptTraceback` (§22 of the inventory) as a
Python-traceback-style stack of frames. This is consumed by the
Trainer's Traceback tab (brief `05-05`) and any future location that
references a traceback path.

## Why this exists

§22 of the inventory: PromptTraceback is operad's optim-layer
counterpart to a Python traceback. Today the data is saved (
`Trainer.fit` → `traceback.save(path)`) but the dashboard has no
viewer.

## Files to touch

- New: `apps/frontend/src/components/algorithms/trainer/prompt-traceback-reader.tsx`.
- New: `apps/frontend/src/components/algorithms/trainer/prompt-traceback-reader.test.tsx`.
- New backend route:
  `apps/dashboard/operad_dashboard/routes/traceback.py` —
  `GET /runs/{run_id}/traceback.ndjson` (returns the NDJSON content
  as JSON array of frames).
- `apps/dashboard/operad_dashboard/app.py` — register the route.

## Contract reference

`00-contracts.md` §13 (folder convention), §15 (`traceback_path`),
§22 inventory shape.

## Implementation steps

### Step 1 — Backend route

```python
@router.get("/runs/{run_id}/traceback.ndjson")
async def get_traceback(request: Request, run_id: str) -> JSONResponse:
    info = request.app.state.observer.registry.get(run_id)
    if info is None or not info.traceback_path:
        return _not_found("no traceback for this run")
    path = Path(info.traceback_path)
    if not path.exists():
        return _not_found("traceback file missing on disk")
    frames = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return JSONResponse({"frames": frames})
```

### Step 2 — Component

Render the frames as a vertical stack from most recent to least
recent (matches Python traceback convention):

```
┌─ frame #3 (most recent) ──────────────────────────────────────┐
│  agent: research_analyst.stage_0.role                         │
│  optimizer: TextualGradientDescent · step 4                   │
│  severity: medium · langfuse →                                │
│                                                                │
│  > The reasoner produced a 4-bullet answer where 2 bullets    │
│  > were redundant; soften the rules to allow conciseness.     │
│                                                                │
│  ▾ expand prompt + i/o (markdown)                              │
└────────────────────────────────────────────────────────────────┘

frame #2 ...
frame #1 ...
```

Per frame:
- Header: agent path + optimizer step + severity chip.
- Body: gradient `message` rendered as markdown.
- Expand: full prompt + I/O, also markdown.
- Footer: Langfuse deep-link to the critic invocation.

### Step 3 — Component shape

```tsx
export interface PromptTracebackReaderProps {
  runId: string;
}

export function PromptTracebackReader({ runId }: PromptTracebackReaderProps) {
  const query = useQuery({
    queryKey: ["traceback", runId],
    queryFn: () => fetch(`/runs/${runId}/traceback.ndjson`).then(r => r.json()),
  });
  // ...
}
```

### Step 4 — Empty state

If the route returns 404, render an `EmptyState`:

```
no traceback recorded
this run did not save a PromptTraceback;
add ptb.PromptTraceback.from_run(...).save(path) to your training script
```

## Design alternatives

1. **Render frames newest-first vs oldest-first.** Recommendation:
   newest-first. Matches Python's convention; users expect the
   "deepest" frame at the top.
2. **Inline expand vs full-page view.** Recommendation: inline. The
   tab already has a constrained layout; full-page is overkill.

## Acceptance criteria

- [ ] On a Trainer run with a traceback, the Traceback tab renders
  the frames.
- [ ] Each frame has agent path + optimizer step + severity chip.
- [ ] Each frame's body renders markdown.
- [ ] Expand reveals the full prompt + I/O.
- [ ] Langfuse deep-link works when manifest base URL is set.
- [ ] No traceback → empty state.
- [ ] `pnpm test --run` and `uv run pytest apps/dashboard/tests/`
  pass.

## Test plan

- `prompt-traceback-reader.test.tsx`: 3-frame fixture; assert order
  (newest first); assert expand toggles.
- `apps/dashboard/tests/test_traceback.py`: route test with a
  fixture NDJSON file.

## Stretch goals

- "Step into" a frame: clicking opens the parameter drawer at that
  frame's parameter and gradient.
- Frame filter chips: `severity=high` only, `agent_path=...` only.
- Export traceback as Python-style text for embedding in PR
  descriptions.
