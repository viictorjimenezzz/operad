"""`Trace` — a captured run of an agent graph.

A `Trace` is the reproducibility artefact: it carries the graph
topology, one `OperadOutput` per invoked agent (in call order), and
enough metadata to replay against new metrics without touching any
LLM. Populated by `TraceObserver`, which subscribes to the observer
registry and snapshots the run at the root's terminal event.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.graph import TypeRegistry, from_json as _graph_from_json
from ..core.output import OperadOutput
from ..utils.errors import BuildError
from ..utils.hashing import hash_schema
from .observers.base import AgentEvent

if TYPE_CHECKING:
    from ..core.agent import Agent
    from ..eval import EvalReport
    from ..metrics.base import Metric


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
        cls,
        path: str | Path,
        *,
        type_registry: TypeRegistry | None = None,
        agent: "Agent[Any, Any] | None" = None,
    ) -> "Trace":
        """Load a trace written by `save`. Auto-detects JSON vs NDJSON.

        When ``agent`` is supplied, compares each step's recorded
        ``hash_output_schema`` against the current schema hash of the
        agent subtree at the same path and emits a ``UserWarning`` if
        any step has drifted.
        """
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
        trace = cls.model_validate(data)
        if agent is not None:
            drift = _collect_drift(trace, agent)
            if drift:
                paths = ", ".join(d[0] for d in drift)
                warnings.warn(
                    f"schema_drift: {len(drift)} step(s) differ from current agent "
                    f"output schema ({paths})",
                    category=UserWarning,
                    stacklevel=2,
                )
        return trace

    def rehydrate_graph(self, registry: TypeRegistry | None = None) -> Any:
        """Rebuild the `AgentGraph` from the stored dict."""
        return _graph_from_json(self.graph, registry)

    async def replay(
        self,
        agent: "Agent[Any, Any]",
        metrics: "list[Metric]",
        *,
        strict: bool = True,
        expected: "BaseModel | None" = None,
        predicted_cls: "type[BaseModel] | None" = None,
        expected_cls: "type[BaseModel] | None" = None,
    ) -> "EvalReport":
        """Re-score this trace against ``agent``'s ``metrics`` with a drift gate.

        Raises ``BuildError("schema_drift", …)`` when any step's recorded
        ``hash_output_schema`` differs from the corresponding leaf's
        current schema. Pass ``strict=False`` to downgrade to a warning
        and tag the returned report with ``summary["schema_drift"] = 1.0``.
        """
        from .replay import replay as _replay

        drift = _collect_drift(self, agent)
        if drift:
            paths = ", ".join(d[0] for d in drift)
            message = (
                f"output schema changed since trace was captured "
                f"({len(drift)} step(s): {paths})"
            )
            if strict:
                raise BuildError(
                    "schema_drift", message, agent=type(agent).__name__
                )
            warnings.warn(
                f"schema_drift: {message}",
                category=UserWarning,
                stacklevel=2,
            )
        report = await _replay(
            self,
            metrics,
            expected=expected,
            predicted_cls=predicted_cls,
            expected_cls=expected_cls,
        )
        if drift:
            report.summary["schema_drift"] = 1.0
        return report


def _collect_drift(
    trace: "Trace", agent: "Agent[Any, Any]"
) -> list[tuple[str, str, str]]:
    """Return ``(agent_path, recorded_hash, current_hash)`` for drifted steps.

    Steps whose recorded hash is empty (error placeholders) are skipped,
    as are steps resolving to an agent without an ``output`` attribute
    (mid-graph composites with no ``Output`` to hash).
    """
    from ..core.agent import _labelled_tree

    index = {path: node for path, node in _labelled_tree(agent)}
    drifted: list[tuple[str, str, str]] = []
    for step in trace.steps:
        recorded = step.output.hash_output_schema
        if not recorded:
            continue
        resolved = index.get(step.agent_path)
        if resolved is None:
            drifted.append((step.agent_path, recorded, ""))
            continue
        out_cls = getattr(resolved, "output", None)
        if out_cls is None or not isinstance(out_cls, type):
            continue
        current = hash_schema(out_cls)
        if current != recorded:
            drifted.append((step.agent_path, recorded, current))
    return drifted


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
