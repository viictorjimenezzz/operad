# Feature · `trace_diff(a, b)` — compare two runs

**Addresses.** E-16 (ISSUES.md) + `TODO_TRACE_DIFF` in `missing.py`.

`Agent.diff(other)` compares two agents. Add the dynamic sibling:
given two `Trace`s captured from runs of the same (or compatible)
graph, produce a human-readable per-step delta.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-16.
- `operad/runtime/trace.py` (`Trace`, `TraceStep`).
- `operad/core/diff.py` (`AgentDiff` — mirror its rendering style).

---

## Proposal

### API

```python
# operad/runtime/trace_diff.py (new)
from pydantic import BaseModel

class TraceStepDelta(BaseModel):
    agent_path: str
    status: Literal["unchanged", "changed", "added", "removed"]
    prev_hash_prompt: str = ""
    next_hash_prompt: str = ""
    prev_hash_input: str = ""
    next_hash_input: str = ""
    prev_latency_ms: float = 0.0
    next_latency_ms: float = 0.0
    prev_response_dump: dict = {}
    next_response_dump: dict = {}
    # A field-level diff would be nice later; v1 ships the coarse view.


class TraceDiff(BaseModel):
    prev_run_id: str
    next_run_id: str
    prev_hash_graph: str
    next_hash_graph: str
    graphs_match: bool
    steps: list[TraceStepDelta]
    # Render helpers:
    def __str__(self) -> str: ...
    def _repr_html_(self) -> str: ...


def trace_diff(prev: Trace, next: Trace) -> TraceDiff:
    """Pairwise compare two traces, step by step.

    Steps are matched by `agent_path`; `status="added"` when only the
    next trace has the path; `status="removed"` when only the prev
    does; `status="changed"` when any hash differs or latency delta
    exceeds a threshold; else `"unchanged"`.
    """
```

### Rendering

`__str__` produces a compact text view:

```
trace_diff 7a3f → b91c
graph:   unchanged
step 1   Root.reasoner          unchanged   (12ms → 14ms)
step 2   Root.classifier        changed     prompt hash diff; latency +8ms
step 3   Root.extractor         unchanged
```

`_repr_html_` emits a small HTML table for notebooks, mirroring
`AgentDiff._repr_html_`'s approach.

### Use case

```python
prev = Trace.load("run-2026-04-21.json")
next = Trace.load("run-2026-04-23.json")
print(trace_diff(prev, next))
```

This is the core workflow for hunting regressions after a prompt or
model change.

---

## Required tests

`tests/test_trace_diff.py`:

1. Two identical traces → all steps `"unchanged"`.
2. A step where `hash_prompt` differs → `"changed"` with correct
   prev/next hashes recorded.
3. A step removed in `next` → `"removed"` with empty next fields.
4. A step added in `next` → `"added"`.
5. Graph-hash mismatch sets `graphs_match=False`.

Offline-only; construct Traces via `Trace.model_validate` on fixture
JSON.

---

## Scope

- New: `operad/runtime/trace_diff.py`.
- Edit: `operad/runtime/__init__.py` re-exports.
- Edit: `operad/__init__.py` re-exports `trace_diff`, `TraceDiff`.
- New: `tests/test_trace_diff.py`.
- Edit: `CLAUDE.md` — mention under "introspection" alongside
  `Agent.diff`.

Do NOT:
- Compare agent state. That's `Agent.diff`. `trace_diff` is purely
  about captured runs.
- Try to render a deep Pydantic diff of responses in v1 — keep
  `prev_response_dump` / `next_response_dump` raw and let users pick
  their differ. A later pass can add field-level rendering.

---

## Acceptance

- `uv run pytest tests/` green.
- `trace_diff(t, t)` has all-unchanged steps.
- `trace_diff(t1, t2)` rendered in a notebook produces a legible
  HTML table.

---

## Watch-outs

- Path matching is by exact `agent_path`. If the same agent ran
  twice in `t1` (e.g. BestOfN fan-out) and differently many times
  in `t2`, step matching is ambiguous. For v1, match in order within
  the same path; document the limitation.
- Trace steps may have `error` instead of output. Render those
  specially — don't diff empty hashes.
- Latency threshold for `changed` — default 0.0 (any delta counts).
  Configurable via `trace_diff(..., latency_tolerance_ms=...)`.
