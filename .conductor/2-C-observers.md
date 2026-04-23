# Phase 2 · Stream C — Observer protocol, Rich TUI, JSONL writer

**Goal.** Give every `Agent.invoke` a pre/post hook so observers can
build dashboards, write logs, and accumulate cost/token metrics
without modifying agents.

**Owner:** one agent.
**Depends on.** Stream A (error taxonomy, config knobs).
**Required by.** Stream D (evaluation / cost metrics subscribe to
events).
**Addresses:** C-5.

---

## Scope

### Files you will create
- `operad/runtime/observers/__init__.py`
- `operad/runtime/observers/base.py` — `Observer` protocol,
  `ObserverRegistry`, `AgentEvent` dataclass, `_RUN_ID` + `_PATH_STACK`
  context vars.
- `operad/runtime/observers/jsonl.py` — `JsonlObserver`.
- `operad/runtime/observers/rich.py` — `RichDashboardObserver`.
- `operad/runtime/observers/otel.py` — thin stub (no hard OTel dep).
- `tests/test_observers.py`.
- `examples/observer_demo.py`.

### Files you will edit
- `operad/core/agent.py` — one small edit inside `invoke` to emit
  `start` / `end` / `error` events and maintain the path stack.
- `operad/__init__.py` — export `Observer`, `JsonlObserver`,
  `RichDashboardObserver`.
- `pyproject.toml` — add an optional dependency group `observers`
  containing `rich`. Do NOT add `rich` to base deps.

### Files to leave alone
- Everything under `agents/` and `algorithms/`.

---

## Design direction

### `AgentEvent`

```python
@dataclass
class AgentEvent:
    run_id: str
    agent_path: str            # e.g. "ReAct.reasoner"
    kind: Literal["start", "end", "error"]
    input: BaseModel | None
    output: BaseModel | None
    error: BaseException | None
    started_at: float          # monotonic
    finished_at: float | None
    metadata: dict[str, Any]   # reserved for backend latency, tokens, …
```

### `Observer` protocol

```python
@runtime_checkable
class Observer(Protocol):
    async def on_event(self, event: AgentEvent) -> None: ...
```

Single method, async, so synchronous observers wrap trivially and
async ones (HTTP webhooks, OTel exporters) stay native.

### `ObserverRegistry`

Singleton list-of-observers. `notify(event)` iterates and isolates
errors (`try/except` per observer) so a broken observer can't break
the pipeline.

### Agent.invoke hook

Minimal edit. Use two context vars: `_RUN_ID` for the root run
correlation and `_PATH_STACK` for the current invocation path (mirrors
the tracer's stack pattern in `build.py`).

```python
async def invoke(self, x: In) -> Out:
    tracer = _TRACER.get()
    if tracer is not None:
        return await tracer.record(self, x)    # no events during trace

    run_id = _RUN_ID.get() or uuid.uuid4().hex
    parent = _PATH_STACK.get()
    path = f"{parent}.{_attr_name_hint(self)}" if parent else type(self).__name__

    start = time.monotonic()
    tok_r = _RUN_ID.set(run_id); tok_p = _PATH_STACK.set(path)
    try:
        await observers.notify(AgentEvent(run_id, path, "start", x, None, None, start, None, {}))
        # existing built/input-check/forward/output-check logic
        ...
        await observers.notify(AgentEvent(run_id, path, "end", x, y, None, start, time.monotonic(), {}))
        return y
    except BaseException as e:
        await observers.notify(AgentEvent(run_id, path, "error", x, None, e, start, time.monotonic(), {}))
        raise
    finally:
        _RUN_ID.reset(tok_r); _PATH_STACK.reset(tok_p)
```

`_attr_name_hint` can inspect the parent's `_children` or fall back to
`type(self).__name__`. Don't over-engineer this; path names are for
humans.

### `JsonlObserver`

One-line-per-event NDJSON writer. Events serialise via
`.model_dump(mode="json")` for Pydantic inputs/outputs; serialise error
with `str(e)` + `type(e).__name__`. Open the file in append mode and
flush on every event — small perf cost, huge debug value.

### `RichDashboardObserver`

Live tree of active agents using `rich.live.Live` + `rich.tree.Tree`,
status per path (running / ok / error). Gracefully degrade if `rich`
isn't installed: `try: import rich; except ImportError: ...` and raise
a clear instruction to install the optional group.

### `OtelObserver`

Stub. `# TODO: implement when we take an OTel dep`. Import guarded,
method is a no-op. The point is to show the seam.

---

## Tests

- Registering an observer and calling a built leaf emits `start` then
  `end`.
- Raising in `forward` emits `start` then `error`, not `end`.
- Observer exceptions don't propagate.
- No events emitted during `build()` (`_TRACER` set).
- `JsonlObserver` writes valid NDJSON; parse it back and assert fields.
- Nested composite invocation produces events with dotted paths.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/observer_demo.py` runs a Pipeline with a `JsonlObserver`
  and produces a readable log.

---

## Watch-outs

- Do NOT add `rich` to base deps; optional group only.
- Do NOT emit events during tracing (guard with `_TRACER.get() is not None`).
- Context vars must be reset even on exception — use `try/finally`.
- Keep the `Agent.invoke` edit small and obvious; two strings
  (imports) and ~10 lines of flow. Anything bigger signals scope creep.
