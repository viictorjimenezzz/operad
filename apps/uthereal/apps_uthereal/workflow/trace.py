from __future__ import annotations

"""Owner: 1-5-trace-feedback-models.

Workflow trace models and observer for the uthereal bridge.
"""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from operad.core.output import OperadOutput
from operad.runtime.observers.base import AgentEvent, Event, registry


_IntentDecision = Literal[
    "DIRECT_ANSWER",
    "RAG_NEEDED",
    "SAFEGUARD_REJECTED",
    "CHAR_LIMIT_REJECTED",
]


def _epoch() -> datetime:
    return datetime.fromtimestamp(0, tz=UTC)


class TraceFrame(BaseModel):
    """One leaf invocation captured from an operad run."""

    step_name: str = ""
    agent_class: str = ""
    leaf_role: str = ""
    leaf_task: str = ""
    leaf_rules: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    hash_prompt: str = ""
    hash_input: str = ""
    hash_output_schema: str = ""
    run_id: str = ""
    started_at: datetime = Field(default_factory=_epoch)
    finished_at: datetime = Field(default_factory=_epoch)
    parent_step: str | None = None

    model_config = ConfigDict(frozen=True)


class WorkflowTrace(BaseModel):
    """A deterministic sequence of workflow leaf invocations."""

    trace_id: str = ""
    entry_id: str = ""
    frames: list[TraceFrame] = Field(default_factory=list)
    final_answer_text: str = ""
    intent_decision: _IntentDecision = "DIRECT_ANSWER"
    sealed: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(frozen=True)

    def seal(self) -> "WorkflowTrace":
        """Compute the trace id from frames and return a sealed copy."""

        frames_json = [
            frame.model_dump(mode="json", by_alias=False) for frame in self.frames
        ]
        trace_id = sha256(_canonical_json(frames_json).encode("utf-8")).hexdigest()[
            :16
        ]
        started_at = self.started_at
        finished_at = self.finished_at
        if self.frames:
            started_at = started_at or self.frames[0].started_at
            finished_at = finished_at or self.frames[-1].finished_at
        return self.model_copy(
            update={
                "trace_id": trace_id,
                "sealed": True,
                "started_at": started_at,
                "finished_at": finished_at,
                "frames": list(self.frames),
            }
        )

    def find_step(self, step_name: str) -> TraceFrame:
        """Return the last frame for a step name, or raise ``KeyError``."""

        for frame in reversed(self.frames):
            if frame.step_name == step_name:
                return frame
        raise KeyError(step_name)

    def to_jsonl(self, path: Path) -> None:
        """Write trace metadata followed by one JSON frame per line."""

        trace = self if self.sealed else self.seal()
        header = {
            "trace_id": trace.trace_id,
            "entry_id": trace.entry_id,
            "intent_decision": trace.intent_decision,
            "final_answer_text": trace.final_answer_text,
            "started_at": _json_datetime(trace.started_at),
            "finished_at": _json_datetime(trace.finished_at),
        }
        lines = [_canonical_json(header)]
        lines.extend(
            _canonical_json(frame.model_dump(mode="json"))
            for frame in trace.frames
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def from_jsonl(cls, path: Path) -> "WorkflowTrace":
        """Load a sealed trace from JSONL written by ``to_jsonl``."""

        header: dict[str, Any] = {}
        frames: list[TraceFrame] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if "step_name" in record:
                frames.append(TraceFrame.model_validate(record))
            else:
                header = record

        trace = cls(
            trace_id=str(header.get("trace_id", "")),
            entry_id=str(header.get("entry_id", "")),
            frames=frames,
            final_answer_text=str(header.get("final_answer_text", "")),
            intent_decision=header.get("intent_decision", "DIRECT_ANSWER"),
            started_at=_parse_optional_datetime(header.get("started_at")),
            finished_at=_parse_optional_datetime(header.get("finished_at")),
        )
        return trace.seal()

    def to_blamer_summary(self, *, max_field_chars: int = 600) -> str:
        """Render a compact, deterministic trace summary for the Blamer."""

        sections: list[str] = []
        for frame in self.frames:
            input_json = _canonical_json(frame.input)
            output_json = _canonical_json(frame.output)
            sections.append(
                "\n".join(
                    [
                        f"=== {frame.step_name} ({frame.agent_class}) ===",
                        f"role: {_truncate(frame.leaf_role, max_field_chars)}",
                        f"task: {_truncate(frame.leaf_task, max_field_chars)}",
                        f"input:  {_truncate(input_json, max_field_chars)}",
                        f"output: {_truncate(output_json, max_field_chars)}",
                    ]
                )
            )
        return "\n\n".join(sections)


class WorkflowTraceObserver:
    """An operad observer that captures leaf invocations as trace frames."""

    def __init__(self, *, entry_id: str) -> None:
        self._entry_id = entry_id
        self._frames: list[TraceFrame] = []

    @property
    def trace(self) -> WorkflowTrace:
        """Return the current unsealed trace snapshot."""

        started_at = self._frames[0].started_at if self._frames else None
        finished_at = self._frames[-1].finished_at if self._frames else None
        return WorkflowTrace(
            entry_id=self._entry_id,
            frames=list(self._frames),
            started_at=started_at,
            finished_at=finished_at,
        )

    async def on_event(self, event: Event) -> None:
        """Record one frame for each successful leaf ``end`` event."""

        if not isinstance(event, AgentEvent):
            return
        if event.kind != "end" or event.metadata.get("kind") != "leaf":
            return
        envelope = event.output
        if not isinstance(envelope, OperadOutput):
            return

        response = envelope.response
        finished_at = (
            event.finished_at if event.finished_at is not None else event.started_at
        )
        frame = TraceFrame(
            step_name=event.agent_path,
            agent_class=str(event.metadata.get("class_name", "")),
            leaf_role=str(event.metadata.get("role", "")),
            leaf_task=str(event.metadata.get("task", "")),
            leaf_rules=list(event.metadata.get("rules", [])),
            input=_dump_model(event.input),
            output=_dump_model(response),
            latency_ms=float(envelope.latency_ms),
            hash_prompt=envelope.hash_prompt,
            hash_input=envelope.hash_input,
            hash_output_schema=envelope.hash_output_schema,
            run_id=event.run_id,
            started_at=_from_timestamp(event.started_at),
            finished_at=_from_timestamp(finished_at),
            parent_step=_parent_step(event.agent_path),
        )
        self._frames.append(frame)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _dump_model(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return {}


def _from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=UTC)


def _json_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _parent_step(step_name: str) -> str | None:
    if "." not in step_name:
        return None
    return step_name.rsplit(".", 1)[0]


def _truncate(value: str, max_field_chars: int) -> str:
    cap = max(0, max_field_chars)
    if len(value) <= cap:
        return value
    return f"{value[:cap]}…[truncated, total={len(value)} chars]"


__all__ = [
    "TraceFrame",
    "WorkflowTrace",
    "WorkflowTraceObserver",
    "registry",
]
