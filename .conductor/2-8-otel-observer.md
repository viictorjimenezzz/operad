# 2 · 8 — Real OpenTelemetry observer

**Addresses.** O1 (replace the `OtelObserver` stub with a working
OpenTelemetry implementation).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (observability as the reproducibility
  substrate).
- `operad/runtime/observers/otel.py` — current stub (TODO marker).
- `operad/runtime/observers/base.py` — `Observer` protocol, `AgentEvent`
  shape, registry.
- `operad/runtime/observers/rich_live.py` (if present) or
  `operad/runtime/observers/trace.py` — reference implementation for
  how an observer consumes `AgentEvent`.
- `operad/core/output.py` — the `OperadOutput` envelope whose seven
  `hash_*` fields map onto span attributes.
- `pyproject.toml` — optional-extras section; `[observers]` is already
  present.

---

## Proposal

Replace the stub with an observer that emits one OTel span per
`start → end` pair (and an error span on `error`), carrying the operad
reproducibility hashes as span attributes. Chunk events are counter
increments, not spans.

### Import guard

`opentelemetry` lives under a new optional extra `[otel]`. Core operad
must remain importable without it — today's stub already does this.
The new observer uses a module-local lazy import:

```python
# operad/runtime/observers/otel.py

from __future__ import annotations

import time
from typing import Any
from .base import AgentEvent


class OtelObserver:
    """Emit OpenTelemetry spans for operad AgentEvents.

    Requires the `opentelemetry-api` + `opentelemetry-sdk` extras.
    Construction raises RuntimeError with a clear install hint if
    `opentelemetry` is unimportable.
    """

    def __init__(self, *, tracer_name: str = "operad") -> None:
        try:
            from opentelemetry import trace as _ot
        except ImportError as e:
            raise RuntimeError(
                "OtelObserver requires the `[otel]` extra. "
                "Install with: `pip install operad[otel]`."
            ) from e
        self._trace = _ot
        self._tracer = _ot.get_tracer(tracer_name)
        self._spans: dict[tuple[str, str], Any] = {}  # (run_id, agent_path) → span

    async def on_event(self, event: AgentEvent) -> None: ...
```

### Event → span mapping

| `event.kind` | Span action |
|--------------|-------------|
| `start`      | Open a new span named `event.agent_path`; stash keyed by `(run_id, agent_path)`. Set attributes from envelope/metadata. |
| `end`        | Look up the open span, set `end` attributes + `set_status(OK)`, `span.end()`. |
| `error`      | Look up the open span (or open one inline if absent), `record_exception`, `set_status(ERROR, description=...)`, `span.end()`. |
| `chunk`      | Increment a counter attribute `operad.chunks` on the open span; no new span. |

### Attribute set

On `start`:

- `operad.run_id` = `event.run_id`
- `operad.agent_path` = `event.agent_path`
- `operad.is_root` = `bool(event.metadata.get("is_root"))`
- `operad.hash_graph` = `event.metadata.get("hash_graph", "")`
- `operad.hash_input` = `hash_json(event.input.model_dump(mode="json"))`
  if `event.input is not None`

On `end` (when `event.output` is an `OperadOutput`):

- `operad.hash_prompt` = `envelope.hash_prompt`
- `operad.hash_output_schema` = `envelope.hash_output_schema`
- `operad.hash_input` = `envelope.hash_input`
- `operad.hash_config` = `envelope.hash_config`
- `operad.hash_model` = `envelope.hash_model`
- `operad.hash_graph` = `envelope.hash_graph`
- `operad.latency_ms` = `envelope.latency_ms`
- `operad.prompt_tokens` = `envelope.prompt_tokens`
- `operad.completion_tokens` = `envelope.completion_tokens`

Never attach the raw input or output payload as a span attribute — only
hashes. A caller who wants the payload pulls it from the `Trace`.

### Parent-span linkage

OTel has its own active span context. When the root-run `start` event
fires, capture the parent context via `trace.set_span_in_context` so
child spans nest correctly. If users already run under a parent OTel
context (e.g. from a web server), `get_current_span()` returns it and
operad spans nest naturally as children — no special work.

### `pyproject.toml`

Add:

```toml
[project.optional-dependencies]
otel = [
  "opentelemetry-api>=1.24",
  "opentelemetry-sdk>=1.24",
]
```

Leave the existing `[observers]` extra untouched; `[otel]` is a
separate axis.

### API entry point (optional helper)

Add a tiny convenience:

```python
# operad/runtime/observers/__init__.py (if the factory doesn't exist yet)

def _maybe_otel():
    try:
        from .otel import OtelObserver
        return OtelObserver()
    except RuntimeError:
        return None
```

Not required — callers can `from operad.runtime.observers import
OtelObserver; registry.register(OtelObserver())` directly.

---

## Required tests

`tests/test_observer_otel.py` (new) — all tests `@pytest.mark.skipif`
when `opentelemetry` is not installed.

1. **Span per leaf.** Build a two-stage Pipeline with FakeLeaves;
   register `OtelObserver` against an `InMemorySpanExporter`; invoke;
   assert two spans exist, one per leaf, named after the agent paths.
2. **Span attributes.** For the root span, check the listed OTel
   attributes (`operad.hash_graph`, `operad.hash_prompt`,
   `operad.latency_ms`, …) are present and non-empty.
3. **Error path.** A leaf raises; the corresponding span has
   `Status(ERROR)` and a recorded exception event.
4. **No payload leakage.** Confirm no attribute matches the raw
   input/output string (using `isinstance(attr, str)` + a
   `SPECIFIC_PAYLOAD_VALUE` substring check).
5. **Missing `opentelemetry`.** A unit test that patches
   `sys.modules["opentelemetry"] = None` (or removes it) and asserts
   `OtelObserver()` raises `RuntimeError` with a descriptive message.

Helper: tests use
`opentelemetry.sdk.trace.export.InMemorySpanExporter` +
`SimpleSpanProcessor` to capture spans in-memory.

---

## Scope

**New files.**
- `tests/test_observer_otel.py`.

**Edited files.**
- `operad/runtime/observers/otel.py` — replace stub with full impl.
- `pyproject.toml` — add `[otel]` optional-dependencies entry.

**Must NOT touch.**
- `operad/runtime/observers/base.py` — the observer protocol and
  registry stay stable.
- Other observers (`trace.py`, `rich_live.py`, etc.).
- `operad/core/`.
- Any other Wave-2 file.

---

## Acceptance

- `uv run pip install -e '.[otel]'` succeeds.
- `uv run pytest tests/test_observer_otel.py` green when
  `opentelemetry` is installed; the whole test module skips cleanly
  when it isn't.
- `uv run pytest tests/` green under default extras (no otel).
- `uv run python -c "import operad"` works without otel installed.
- `python -c "from operad.runtime.observers import OtelObserver;
  OtelObserver()"` with no otel raises `RuntimeError` mentioning
  `[otel]`.

---

## Watch-outs

- **Span lookup key.** Use `(run_id, agent_path)` as the stash key.
  The same `agent_path` may appear in multiple concurrent runs; keying
  on just `agent_path` would cross streams.
- **`finally` span-close.** Always close the stashed span on `end` or
  `error`. If a caller's program crashes between start and end (no
  event ever fires), the span is leaked in `self._spans` — acceptable
  for v1; document that `clear()` can be called manually, or rely on
  process teardown. Don't implement complex leak detection here.
- **`record_exception`.** Accepts an exception *instance*; `AgentEvent.
  error` carries one. Pass it directly; don't stringify first.
- **OTel version pinning.** `>=1.24` is safe as of this PR; the stable
  trace API hasn't churned since 1.0. Don't upper-bound pin to avoid
  breaking downstream combinations.
- **Observer failures are silent.** The registry's `notify()` swallows
  observer exceptions (line 58 of `observers/base.py`). A broken OTel
  exporter won't break the pipeline. This also means: test observer
  behaviour with direct assertions on the exporter, not by expecting
  errors to surface.
- **Chunk counter semantics.** `operad.chunks` is the count of `chunk`
  events received on the span. Do NOT attempt to aggregate token
  counts from chunks — those live on `OperadOutput` at `end` time.
- **Operad is the tracer name.** `trace.get_tracer("operad")` so
  downstream dashboards can filter by service. Accept an override kwarg
  for callers who want a different tracer name.
