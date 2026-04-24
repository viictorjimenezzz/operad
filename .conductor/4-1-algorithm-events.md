# 4 · 1 — Algorithm event schema + emission

**Addresses.** H-1 (algorithms emit no events), A-1 (no algorithm event
schema). See [`../ISSUES.md`](../ISSUES.md) Group A.

**Depends on.** Nothing in Wave 4 — this brief is the first mover.
(Phase 0 hygiene fixes must be merged; assume they are.)

**Blocks.** 5-2 (dashboard) — the dashboard consumes these events.
Also consumed by 5-1 (`auto_tune`) to surface generation progress.

---

## Required reading

- `VISION.md` §7 (iteration-4 observability commitment) and §5.3 (the
  build step).
- `operad/runtime/observers/base.py` — the existing `AgentEvent`
  dataclass, the `Observer` Protocol, the `ObserverRegistry`, and the
  context vars (`_RUN_ID`, `_PATH_STACK`, `_RETRY_META`).
- `operad/runtime/observers/{jsonl,rich,otel}.py` — three existing
  observers that today only dispatch on `AgentEvent`.
- Every file under `operad/algorithms/` — each currently runs with no
  `registry.notify` calls.
- `tests/runtime/test_observers.py` — patterns for writing an observer
  test using a `MemObs` class that just appends events to a list.

---

## Goal

Dashboards today see leaf invocations (`AgentEvent`) but not algorithm
boundaries. An Evolutionary run of 4 generations × 8 individuals fires
32 `AgentEvent`s per generation and zero events telling you a
generation completed, which individual won, or which mutation op was
applied. Add a second event type — `AlgorithmEvent` — that algorithms
emit at their natural boundaries, and widen the observer protocol to
carry the union.

## Scope

### New module: `operad/runtime/events.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

AlgoKind = Literal[
    "algo_start", "algo_end", "algo_error",
    "generation", "round", "cell", "candidate", "iteration",
]

@dataclass
class AlgorithmEvent:
    run_id: str               # same run_id as enclosing AgentEvents
    algorithm_path: str       # dotted name of the algorithm class
    kind: AlgoKind
    payload: dict[str, Any]   # event-type-specific, JSON-serialisable
    started_at: float
    finished_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Payload schemas (documented in docstrings, not enforced via Pydantic
to keep the event type lightweight):

| `kind`      | payload keys                                             | emitted by |
|-------------|----------------------------------------------------------|------------|
| `generation`| `gen_index:int, population_scores:list[float], survivor_indices:list[int]` | Evolutionary |
| `round`     | `round_index:int, proposal:dict, critique:dict, score:float` | Debate |
| `cell`      | `cell_index:int, parameters:dict, score:float`           | Sweep |
| `candidate` | `candidate_index:int, score:float`                       | BestOfN |
| `iteration` | `iter_index:int, phase:str, score:float\|None`           | SelfRefine, VerifierLoop, AutoResearcher |
| `algo_start`/`algo_end`/`algo_error` | free-form                       | all |

### Widen the observer protocol

In `operad/runtime/observers/base.py`:

```python
Event = AgentEvent | AlgorithmEvent  # at the top of the module

@runtime_checkable
class Observer(Protocol):
    async def on_event(self, event: Event) -> None: ...
```

`ObserverRegistry.notify(event: Event)` accepts either. Do not
bifurcate the method — one bus, two event types.

### Instrument every algorithm

For each of `operad/algorithms/{best_of_n, evolutionary, debate,
sweep, self_refine, verifier_loop, auto_research}.py`:

1. At the start of `run(...)`, emit `algo_start` with the algorithm's
   class name as `algorithm_path`.
2. Emit one event per natural boundary (see payload table above).
3. On success, emit `algo_end` with the final chosen result's score
   (or identifier) in `payload`.
4. On exception, emit `algo_error` with the exception type/message,
   then re-raise.
5. Reuse the enclosing `run_id`: read it from `_RUN_ID.get()` if one
   is already set, otherwise generate a new `uuid4().hex` and set it
   for the duration of the run. Child `AgentEvent`s emitted by nested
   leaf invocations will automatically share the run id.

### Dispatch in existing observers

- `JsonlObserver.on_event` — serialize any `Event` via
  `event.__dict__` or a small helper that tolerates both dataclasses.
- `RichDashboardObserver.on_event` — recognise `AlgorithmEvent` and
  render a separate subtree per algorithm (e.g. "Generation 2/4 —
  population scores 0.8, 0.7, ..."). Do not break the existing
  per-leaf tree.
- `OtelObserver.on_event` — emit a span per `algo_start`/`algo_end`
  pair, with payload keys as span attributes (sanitised per OTel rules).

### Context-var helper

Add a small helper in `operad/runtime/observers/base.py`:

```python
async def emit_algorithm_event(
    kind: AlgoKind, *, algorithm_path: str, payload: dict[str, Any]
) -> None:
    """Fire one AlgorithmEvent on the global registry using the current run_id."""
    ...
```

so algorithm authors don't have to copy the context-var boilerplate.

---

## Verification

- Unit test per observer: `JsonlObserver`/`RichDashboardObserver`/
  `OtelObserver` each cope with `AlgorithmEvent` without raising.
- Integration test per algorithm: run each with a `MemObs` attached
  and assert the event sequence matches the documented shape. E.g. for
  `Evolutionary(generations=2, population_size=4)`: 1 `algo_start` +
  2 `generation` + 1 `algo_end` = 4 events; assert 4 `candidate` or
  score entries in each `generation` payload.
- Backwards compat: every existing observer test in
  `tests/runtime/test_observers.py` still passes untouched.
- `scripts/verify.sh` green.

---

## Out of scope

- The web dashboard (brief 5-2). This brief just emits events; what
  consumes them is a separate concern.
- Cost/slot telemetry (briefs 4-2, 4-3). They emit their own
  update events if useful; do not add them to this schema.
- Nested algorithms (Evolutionary wrapping BestOfN). If `run_id` is
  already set, nested algorithms reuse it — so `algorithm_path`
  differentiates them. No additional stacking rules needed.

---

## Design notes

- Keep `AlgorithmEvent` a `@dataclass`, not a Pydantic model. The
  payload is intentionally untyped so new algorithm kinds can add
  keys without bumping a schema version. The observer is responsible
  for tolerating unknown payload keys.
- Do **not** introduce a second registry. One registry, two event
  types, union in the Protocol signature.
