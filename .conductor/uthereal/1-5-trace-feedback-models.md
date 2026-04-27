# 1-5 — WorkflowTrace, observer, HumanFeedback schema

**Batch:** 1 · **Parallelizable with:** 1-1, 1-2, 1-3, 1-4 · **Depends on:** —

You are building the data structures that flow between the runner, the
human, and the Blamer. C7 (tracing) and C10 (trace shape) are binding.

## Goal

Define `TraceFrame`, `WorkflowTrace`, and `HumanFeedback` as frozen
Pydantic models. Provide `WorkflowTraceObserver`, an operad observer
that captures every leaf invocation as a `TraceFrame`. Provide JSONL
serialization for `WorkflowTrace`.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/workflow/trace.py` | TraceFrame, WorkflowTrace, WorkflowTraceObserver |
| `apps_uthereal/feedback/schema.py` | HumanFeedback model + load/save helpers |
| `apps_uthereal/tests/test_trace.py` | trace observer + serialization tests |
| `apps_uthereal/tests/test_feedback_schema.py` | feedback IO tests |

## API surface

```python
# apps_uthereal/workflow/trace.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from operad.runtime.observers.base import registry, Event  # operad public API


class TraceFrame(BaseModel):
    step_name: str
    agent_class: str
    leaf_role: str
    leaf_task: str
    leaf_rules: list[str]
    input: dict[str, Any]
    output: dict[str, Any]
    latency_ms: float
    hash_prompt: str
    hash_input: str
    hash_output_schema: str
    run_id: str
    started_at: datetime
    finished_at: datetime
    parent_step: str | None = None

    model_config = ConfigDict(frozen=True)


class WorkflowTrace(BaseModel):
    trace_id: str
    entry_id: str
    frames: list[TraceFrame] = Field(default_factory=list)
    final_answer_text: str = ""
    intent_decision: Literal[
        "DIRECT_ANSWER", "RAG_NEEDED", "SAFEGUARD_REJECTED", "CHAR_LIMIT_REJECTED"
    ] = "DIRECT_ANSWER"
    sealed: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def seal(self) -> "WorkflowTrace":
        """Compute trace_id from frames; mark sealed; return new instance.

        After sealing, frames must not be mutated. trace_id =
        sha256(canonical_json(frames))[:16]."""

    def find_step(self, step_name: str) -> TraceFrame:
        """Return the (last) frame for the given step_name; raise KeyError if absent."""

    def to_jsonl(self, path: Path) -> None:
        """Write one TraceFrame per line as JSON, plus a header line with metadata."""

    @classmethod
    def from_jsonl(cls, path: Path) -> "WorkflowTrace":
        """Reconstruct a sealed WorkflowTrace from JSONL."""

    def to_blamer_summary(self, *, max_field_chars: int = 600) -> str:
        """Render the trace as a string for the Blamer's input.

        Format: one section per frame:
            === step_name (agent_class) ===
            role: <truncated leaf_role>
            task: <truncated leaf_task>
            input:  <truncated json>
            output: <truncated json>
        """


class WorkflowTraceObserver:
    """An operad observer that captures every leaf invocation as a TraceFrame.

    Usage (owned by 3-1, but the API is yours):
        async def __call__(self, x):
            obs = WorkflowTraceObserver(entry_id=...)
            registry.register(obs)
            try:
                ...run leaves...
            finally:
                registry.unregister(obs)
            return answer, obs.trace.seal()
    """

    def __init__(self, *, entry_id: str) -> None: ...
    @property
    def trace(self) -> WorkflowTrace: ...
    async def on_event(self, event: Event) -> None: ...


# apps_uthereal/feedback/schema.py
class HumanFeedback(BaseModel):
    """The user's natural-language critique of a final answer.

    `target_path` is optional manual blame; if None, the Blamer agent
    decides. `severity` defaults to 1.0 (full strength).
    """
    trace_id: str
    final_answer_critique: str
    target_path: str | None = None
    severity: float = 1.0
    desired_behavior: str | None = None

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_json(cls, path: Path) -> "HumanFeedback": ...
    def to_json(self, path: Path) -> None: ...
    @classmethod
    def template(cls, trace_id: str) -> "HumanFeedback":
        """Return a default-filled instance for the editor template."""
```

## Implementation notes

- **Frame field selection.** Frames carry agent state snapshots
  (`leaf_role`, `leaf_task`, `leaf_rules`) so the Blamer's input doesn't
  require live agent introspection later. Snapshot at invocation time,
  not after — operad's hash machinery may flush state between calls.
- **Observer wiring.** Operad's `registry.register(observer)` accepts
  any object with `async def on_event(self, event: Event) -> None`. The
  events you care about (`AgentStartEvent`, `AgentEndEvent`,
  `OperadOutput.envelope`) flow through there. Inspect operad's
  `runtime/observers/base.py` for the exact event types and their
  payloads. Filter to leaf-level events; ignore composite/router-level.
- **Determinism.** `to_jsonl` writes UTF-8, no BOM, `\n` line endings,
  ISO-8601 timestamps. Two seals of the same frame list produce equal
  `trace_id`.
- **Header line.** First line of `trace.jsonl` is a JSON object with
  `{trace_id, entry_id, intent_decision, final_answer_text,
  started_at, finished_at}`. Subsequent lines are `TraceFrame`s. The
  parser distinguishes by presence of the `step_name` field.
- **Truncation in `to_blamer_summary`.** Long field values get truncated
  to `max_field_chars` with a `…[truncated, total=N chars]` suffix. Make
  sure the truncation is deterministic (no random middle-ellipsis).
- **JSON coercion.** Frame `input` and `output` dicts come from
  `BaseModel.model_dump(mode="json")`. Already JSON-safe; don't
  re-serialize.

## Acceptance criteria

- [ ] `TraceFrame.model_construct()` returns a default frame.
- [ ] `WorkflowTrace().seal().trace_id` is non-empty and deterministic.
- [ ] Two `WorkflowTrace`s with identical frames have equal `trace_id`.
- [ ] `WorkflowTrace().to_jsonl(p)` then `WorkflowTrace.from_jsonl(p)`
      yields a sealed trace equal to the original.
- [ ] `to_blamer_summary` truncates long fields and never exceeds the
      cap by more than ~30 chars (the suffix length).
- [ ] `WorkflowTraceObserver` accumulates one frame per leaf invocation
      when wired to a small operad pipeline (test in this task using
      operad's `Sequential` with two trivial leaves).
- [ ] `HumanFeedback.template(trace_id)` returns a fully-defaulted
      instance with `final_answer_critique=""`.
- [ ] No imports from `uthereal_*`.

## Tests

- `test_trace_frame_frozen` — assignment raises.
- `test_workflow_trace_seal_is_deterministic` — same frames → same
  trace_id; reorder → different.
- `test_to_jsonl_round_trip` — `from_jsonl(to_jsonl(t)) == t`.
- `test_jsonl_header_first` — first line parses as the metadata header.
- `test_to_blamer_summary_truncates_long_fields`.
- `test_observer_records_one_frame_per_leaf` — wire to a `Sequential` of
  two `FakeLeaf`s under `tape()` and assert frame count + step_names.
- `test_observer_records_input_output_dicts` — assert content matches.
- `test_observer_records_hash_fields` — assert non-empty hashes.
- `test_human_feedback_round_trip` — JSON write/read.
- `test_human_feedback_template_defaults`.
- `test_workflow_trace_find_step_raises_keyerror_on_missing`.

## References

- `operad/runtime/observers/base.py` — Event types and registry API.
- `operad/runtime/trace.py` — `Trace` reference implementation; we're
  building a parallel structure focused on workflow leaves.
- `operad/core/output.py` — `OperadOutput` envelope shape (the source of
  hash fields).
- `operad/agents/conversational/components/title.py` — example of a
  simple leaf you can use in tests.

## Notes

(Append discoveries here as you implement.)
