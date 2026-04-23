"""`Trace` — a captured run of an agent graph.

A `Trace` is the reproducibility artefact: it carries the graph
topology, one `OperadOutput` per invoked agent (in call order), and
enough metadata to replay against new metrics without touching any
LLM. Populated by `TraceObserver`, which subscribes to the observer
registry and snapshots the run at the root's terminal event.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.graph import TypeRegistry, from_json as _graph_from_json
from ..core.output import OperadOutput
from .observers.base import AgentEvent


class TraceStep(BaseModel):
    """One agent invocation inside a run."""

    agent_path: str
    output: OperadOutput[Any]
    error: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Trace(BaseModel):
    """A full run: topology + per-step outputs + root I/O."""

    run_id: str
    graph: dict[str, Any] = Field(default_factory=dict)
    steps: list[TraceStep] = Field(default_factory=list)
    root_input: dict[str, Any] = Field(default_factory=dict)
    root_output: dict[str, Any] = Field(default_factory=dict)
    root_output_type: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- save / load ---------------------------------------------------------

    def save(self, path: str | Path, *, ndjson: bool = False) -> None:
        """Write the trace to `path`. JSON by default; NDJSON when asked.

        NDJSON layout: line 1 is a header (everything except `steps`),
        lines 2..N are one `TraceStep` each. Good for long runs.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not ndjson:
            p.write_text(
                json.dumps(self.model_dump(mode="json"), sort_keys=True, indent=2),
                encoding="utf-8",
            )
            return
        header = self.model_dump(mode="json")
        steps = header.pop("steps", [])
        lines = [json.dumps(header, sort_keys=True)]
        for s in steps:
            lines.append(json.dumps(s, sort_keys=True))
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def load(
        cls, path: str | Path, *, type_registry: TypeRegistry | None = None
    ) -> "Trace":
        """Load a trace written by `save`. Auto-detects JSON vs NDJSON."""
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        stripped = text.lstrip()
        if stripped.startswith("{") and "\n{" in text.strip():
            # NDJSON: one header + one step per line.
            lines = [ln for ln in text.splitlines() if ln.strip()]
            header = json.loads(lines[0])
            header["steps"] = [json.loads(ln) for ln in lines[1:]]
            data = header
        else:
            data = json.loads(text)
        # type_registry is accepted for symmetry and future typed rehydration;
        # OperadOutput[Any] already round-trips via Pydantic's model_validate.
        _ = type_registry
        return cls.model_validate(data)

    def rehydrate_graph(self, registry: TypeRegistry | None = None) -> Any:
        """Rebuild the `AgentGraph` from the stored dict."""
        return _graph_from_json(self.graph, registry)


# --- observer ---------------------------------------------------------------


class TraceObserver:
    """Observer that snapshots one full run into a `Trace`.

    Subscribes to the observer registry. On the root's terminal event
    (`end` or `error`) it records the finished `Trace` under `traces`
    keyed by `run_id` and exposes it via `last()` / `all()`. Child
    events accumulate as `TraceStep`s in invocation order.
    """

    def __init__(self) -> None:
        self._partial: dict[str, dict[str, Any]] = {}
        self.traces: dict[str, Trace] = {}

    def _bucket(self, run_id: str) -> dict[str, Any]:
        b = self._partial.get(run_id)
        if b is None:
            b = {
                "run_id": run_id,
                "graph": {},
                "steps": [],
                "root_input": {},
                "root_output": {},
                "root_output_type": "",
                "started_at": 0.0,
                "finished_at": 0.0,
                "root_path": None,
                "error": None,
            }
            self._partial[run_id] = b
        return b

    async def on_event(self, event: AgentEvent) -> None:
        b = self._bucket(event.run_id)
        is_root = bool(event.metadata.get("is_root"))

        if event.kind == "start":
            if is_root:
                b["root_path"] = event.agent_path
                b["started_at"] = event.started_at
                if event.input is not None:
                    b["root_input"] = event.input.model_dump(mode="json")
                graph_json = event.metadata.get("graph")
                if graph_json is not None:
                    b["graph"] = graph_json
            return

        if event.kind == "end":
            envelope = event.output
            if isinstance(envelope, OperadOutput):
                b["steps"].append(
                    TraceStep(agent_path=event.agent_path, output=envelope)
                )
            if is_root:
                if isinstance(envelope, OperadOutput):
                    b["root_output"] = envelope.response.model_dump(mode="json")
                b["root_output_type"] = event.metadata.get("output_type", "")
                b["finished_at"] = event.finished_at or 0.0
                self._finalize(event.run_id)
            return

        if event.kind == "error":
            b["steps"].append(
                TraceStep(
                    agent_path=event.agent_path,
                    output=OperadOutput[Any].model_construct(
                        response=_Empty(),
                        run_id=event.run_id,
                        agent_path=event.agent_path,
                    ),
                    error=f"{type(event.error).__name__}: {event.error}"
                    if event.error is not None
                    else "error",
                )
            )
            if is_root:
                b["error"] = (
                    f"{type(event.error).__name__}: {event.error}"
                    if event.error is not None
                    else "error"
                )
                b["finished_at"] = event.finished_at or 0.0
                self._finalize(event.run_id)
            return

    def _finalize(self, run_id: str) -> None:
        b = self._partial.pop(run_id, None)
        if b is None:
            return
        b.pop("root_path", None)
        self.traces[run_id] = Trace.model_validate(b)

    def last(self) -> Trace | None:
        if not self.traces:
            return None
        return next(reversed(self.traces.values()))

    def all(self) -> list[Trace]:
        return list(self.traces.values())


class _Empty(BaseModel):
    """Placeholder response for error steps where `y` was never produced."""

    model_config = ConfigDict(extra="allow")


__all__ = ["Trace", "TraceObserver", "TraceStep"]
