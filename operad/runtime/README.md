# operad.runtime — execution + observability spine

This submodule cross-cuts every other one. It captures *what
happened* during a run (traces, costs, streaming chunks) and controls
*how it runs* (concurrency caps, retries, sandboxed launchers). The
observer registry is the single seam through which terminal UI, JSONL
logs, OpenTelemetry spans, and the web dashboard all see the same
events.

Inference and training share this layer wholesale — there is no
training-specific instrumentation. A `Trainer.fit` run is just a
sequence of `Agent.invoke` calls plus a few extra event types
(`algo_start`, `iteration`, `algo_end`, `batch_*`).

---

## Files

| File              | Role                                                                              |
| ----------------- | --------------------------------------------------------------------------------- |
| `slots.py`        | `SlotRegistry`, `acquire`, `set_limit`, `SlotOccupancy`. Per-(backend, host) caps: concurrency + RPM + TPM (sliding window). |
| `events.py`       | The shared event type hierarchy (`AgentEvent`, `AlgorithmEvent`, `BatchEvent`, …).|
| `trace.py`        | `Trace` accumulator + `Trace.load` + `Trace.replay` (with schema-drift warnings). |
| `trace_diff.py`   | `trace_diff(prev, next)` — step-by-step diff for regression hunting.              |
| `replay.py`       | Replay primitives consumed by `operad tail` and `Trace.replay`.                   |
| `retry.py`        | `RetryPolicy` (timeout, max_retries, backoff_base) — wraps the provider call.     |
| `streaming.py`    | `ChunkEvent` token-stream events.                                                 |
| `observers/base.py` | `Observer` protocol + the global `registry`.                                    |
| `observers/jsonl.py`| `JsonlObserver` — one NDJSON line per event; `save()` to file.                  |
| `observers/rich.py` | `RichDashboardObserver` — live terminal TUI; needs `[observers]`.               |
| `observers/otel.py` | `OtelObserver` — real OpenTelemetry spans with hashes as attributes; needs `[otel]`. |
| `launchers/sandbox.py` + `pool.py` + `sandbox_worker.py` | `SandboxedTool` / `SandboxPool` — fresh-subprocess execution for tools or untrusted code. |

## Public API

```python
from operad.runtime import SlotRegistry, acquire, registry, set_limit, SlotOccupancy
from operad.metrics.cost import CostObserver
from operad.runtime.trace import Trace
from operad.runtime.trace_diff import trace_diff
from operad.runtime.streaming import ChunkEvent
from operad.runtime.observers import (
    JsonlObserver, RichDashboardObserver, OtelObserver,
)
from operad.runtime.launchers import SandboxPool
import operad.tracing as tracing  # the watch() one-liner
```

## Smallest meaningful examples

**Per-endpoint slots.**

```python
import operad
operad.set_limit(backend="openai", concurrency=4, rpm=500, tpm=90_000)
```

Three orthogonal caps, all stacked per `(backend, host)`. `concurrency`
is the existing semaphore; `rpm` / `tpm` use a monotonic-clock sliding
window.

**Tracing one block.**

```python
import operad.tracing as tracing
with tracing.watch(jsonl="run.jsonl"):
    out = await agent(x)
# or set OPERAD_TRACE=/tmp/run.jsonl globally
```

**Sandboxed tool execution.**

```python
from operad.runtime.launchers import SandboxPool
pool = SandboxPool(max_workers=4)
result = await pool.run(expensive_fn, *args)
```

**Trace replay with schema-drift detection.**

```python
from operad.runtime.trace import Trace
from operad.metrics import ExactMatch
trace  = Trace.load("run.json", agent=agent)         # warns on schema drift
report = await trace.replay(agent, [ExactMatch()])   # re-score offline
```

## How to extend

| What                            | Where                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| A new observer                  | `observers/<name>.py` — subclass `Observer`, then `registry.register(MyObs())`.       |
| A new event type                | `events.py` — add the dataclass, fire from the producing site.                       |
| A new launcher                  | `launchers/<name>.py` — mirror `SandboxPool`'s shape.                                |
| A new retry policy              | Extend `Resilience` in `core/config.py` — `retry.py` reads it.                       |

## Roadmap

Two launchers are tracked but not yet shipped: an asyncio default and a
macOS Terminal launcher. The sandbox process pool is shipped today.

## Related

- [`../core/`](../core/README.md) — every `Agent.invoke` fires events
  through this registry.
- [`../train/`](../train/README.md) — `TrainerProgressObserver` is a
  built-in observer; `apps/dashboard` reads the same events.
- [`apps/dashboard/`](../../apps/dashboard/README.md) — the web UI
  built on this observer registry.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §13 — full
  observer catalog with output formats.
