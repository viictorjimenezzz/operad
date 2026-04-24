"""In-memory ring buffer of recent operad runs + cached Mermaid graph."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Literal

from operad.core.graph import TypeRegistry, from_json, to_mermaid


RunState = Literal["running", "ended", "error"]

_DEFAULT_CAPACITY = 50


@dataclass
class RunInfo:
    run_id: str
    started_at: float
    last_event_at: float
    state: RunState = "running"
    mermaid: str | None = None


class RunRegistry:
    """Bounded LRU of run_id → RunInfo. Drop-oldest on overflow."""

    def __init__(self, capacity: int = _DEFAULT_CAPACITY) -> None:
        self._capacity = capacity
        self._runs: OrderedDict[str, RunInfo] = OrderedDict()
        self._type_registry = TypeRegistry()

    def __len__(self) -> int:
        return len(self._runs)

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._runs

    def get(self, run_id: str) -> RunInfo | None:
        return self._runs.get(run_id)

    def list(self) -> list[RunInfo]:
        # Newest first.
        return list(reversed(self._runs.values()))

    def observe_agent_event(
        self,
        *,
        run_id: str,
        kind: str,
        timestamp: float,
        metadata: dict[str, Any] | None,
    ) -> None:
        info = self._runs.get(run_id)
        if info is None:
            info = RunInfo(run_id=run_id, started_at=timestamp, last_event_at=timestamp)
            self._runs[run_id] = info
            self._evict_if_needed()
        else:
            self._runs.move_to_end(run_id)
            info.last_event_at = timestamp

        if info.mermaid is None and metadata:
            graph_data = metadata.get("graph")
            if isinstance(graph_data, dict) and graph_data.get("nodes"):
                info.mermaid = self._render_mermaid(graph_data)

        if metadata and metadata.get("is_root"):
            if kind == "end":
                info.state = "ended"
            elif kind == "error":
                info.state = "error"

    def observe_algorithm_event(
        self, *, run_id: str, timestamp: float
    ) -> None:
        info = self._runs.get(run_id)
        if info is None:
            info = RunInfo(run_id=run_id, started_at=timestamp, last_event_at=timestamp)
            self._runs[run_id] = info
            self._evict_if_needed()
        else:
            self._runs.move_to_end(run_id)
            info.last_event_at = timestamp

    def _render_mermaid(self, graph_data: dict[str, Any]) -> str:
        try:
            graph = from_json(graph_data, self._type_registry)
            return to_mermaid(graph)
        except Exception:
            # Type rehydration can fail for dynamically-created classes
            # (test fixtures, REPL). Fall back to a placeholder rather
            # than dropping the whole run.
            return _fallback_mermaid(graph_data)

    def _evict_if_needed(self) -> None:
        while len(self._runs) > self._capacity:
            self._runs.popitem(last=False)


def _fallback_mermaid(graph_data: dict[str, Any]) -> str:
    """Render a Mermaid flowchart from raw graph JSON when type rehydration fails."""
    lines = ["flowchart LR"]
    nodes = graph_data.get("nodes") or []
    for n in nodes:
        path = str(n.get("path", "?"))
        nid = path.replace(".", "_")
        kind = n.get("kind", "leaf")
        in_t = str(n.get("input", "?")).rsplit(".", 1)[-1]
        out_t = str(n.get("output", "?")).rsplit(".", 1)[-1]
        label = f"{path}<br/>{in_t} -> {out_t}"
        if kind == "leaf":
            lines.append(f'    {nid}(("{label}"))')
        else:
            lines.append(f'    {nid}["{label}"]')
    for e in graph_data.get("edges") or []:
        caller = str(e.get("caller", "?")).replace(".", "_")
        callee = str(e.get("callee", "?")).replace(".", "_")
        lines.append(f"    {caller} --> {callee}")
    return "\n".join(lines)
