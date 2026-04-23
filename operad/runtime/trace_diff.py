"""`trace_diff(prev, next)` — compare two captured runs.

Dynamic sibling of `Agent.diff`. Given two `Trace`s from runs of the
same (or compatible) graph, produce a per-step delta: prompt/input
hash changes, latency deltas, added/removed steps, and a graph-hash
match flag.

Step matching: by exact `agent_path`. Duplicate paths in a single
trace (e.g. `BestOfN` fan-out) match in order within that path;
remaining entries become `"added"` or `"removed"`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .trace import Trace, TraceStep


StepStatus = Literal["unchanged", "changed", "added", "removed"]


class TraceStepDelta(BaseModel):
    """One step-level difference between two traces."""

    agent_path: str
    status: StepStatus
    prev_hash_prompt: str = ""
    next_hash_prompt: str = ""
    prev_hash_input: str = ""
    next_hash_input: str = ""
    prev_latency_ms: float = 0.0
    next_latency_ms: float = 0.0
    prev_response_dump: dict[str, Any] = Field(default_factory=dict)
    next_response_dump: dict[str, Any] = Field(default_factory=dict)
    prev_error: str | None = None
    next_error: str | None = None
    reasons: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TraceDiff(BaseModel):
    """Result of `trace_diff(prev, next)`."""

    prev_run_id: str
    next_run_id: str
    prev_hash_graph: str
    next_hash_graph: str
    graphs_match: bool
    steps: list[TraceStepDelta] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __bool__(self) -> bool:
        return (not self.graphs_match) or any(
            s.status != "unchanged" for s in self.steps
        )

    def __str__(self) -> str:
        prev_short = (self.prev_run_id or "-")[:8]
        next_short = (self.next_run_id or "-")[:8]
        lines = [f"trace_diff {prev_short} → {next_short}"]
        graph_line = "unchanged" if self.graphs_match else (
            f"changed  ({self.prev_hash_graph or '-'} → {self.next_hash_graph or '-'})"
        )
        lines.append(f"graph:   {graph_line}")
        if not self.steps:
            lines.append("(no steps)")
            return "\n".join(lines)
        path_w = max(len(s.agent_path) for s in self.steps)
        for i, s in enumerate(self.steps, 1):
            path = s.agent_path.ljust(path_w)
            if s.status == "unchanged":
                tail = f"({s.prev_latency_ms:.1f}ms → {s.next_latency_ms:.1f}ms)"
            elif s.status == "added":
                tail = f"({s.next_latency_ms:.1f}ms)"
            elif s.status == "removed":
                tail = f"({s.prev_latency_ms:.1f}ms)"
            else:
                tail = "; ".join(s.reasons) if s.reasons else ""
            lines.append(f"step {i:<3} {path}  {s.status:<9}  {tail}".rstrip())
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        header_cls = "ok" if self.graphs_match else "bad"
        rows = [
            "<tr>"
            "<th>#</th><th>path</th><th>status</th>"
            "<th>prev hash_prompt</th><th>next hash_prompt</th>"
            "<th>prev hash_input</th><th>next hash_input</th>"
            "<th>prev ms</th><th>next ms</th>"
            "</tr>"
        ]
        for i, s in enumerate(self.steps, 1):
            rows.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td><code>{_esc(s.agent_path)}</code></td>"
                f"<td>{s.status}</td>"
                f"<td><code>{_esc(s.prev_hash_prompt)}</code></td>"
                f"<td><code>{_esc(s.next_hash_prompt)}</code></td>"
                f"<td><code>{_esc(s.prev_hash_input)}</code></td>"
                f"<td><code>{_esc(s.next_hash_input)}</code></td>"
                f"<td>{s.prev_latency_ms:.1f}</td>"
                f"<td>{s.next_latency_ms:.1f}</td>"
                "</tr>"
            )
        graph_row = (
            f"<div>graph: <span class='{header_cls}'>"
            f"{'unchanged' if self.graphs_match else 'changed'}</span>"
            f" ({_esc(self.prev_hash_graph) or '-'} → "
            f"{_esc(self.next_hash_graph) or '-'})</div>"
        )
        prev_short = _esc((self.prev_run_id or "-")[:8])
        next_short = _esc((self.next_run_id or "-")[:8])
        return (
            f"<div><strong>trace_diff</strong> {prev_short} → {next_short}</div>"
            f"{graph_row}"
            f"<table>{''.join(rows)}</table>"
        )


def trace_diff(
    prev: Trace,
    next: Trace,
    *,
    latency_tolerance_ms: float = 0.0,
) -> TraceDiff:
    """Pairwise compare two traces, step by step.

    Steps are matched by `agent_path` in appearance order. A step is
    `"changed"` when `hash_prompt` or `hash_input` differs, the
    latency delta exceeds `latency_tolerance_ms`, or the error status
    differs. Steps only in `next` are `"added"`; steps only in `prev`
    are `"removed"`.
    """
    prev_hash_graph = _trace_hash_graph(prev)
    next_hash_graph = _trace_hash_graph(next)

    prev_by_path: dict[str, list[TraceStep]] = defaultdict(list)
    next_by_path: dict[str, list[TraceStep]] = defaultdict(list)
    for s in prev.steps:
        prev_by_path[s.agent_path].append(s)
    for s in next.steps:
        next_by_path[s.agent_path].append(s)

    seen: set[str] = set()
    ordered_paths: list[str] = []
    for s in next.steps:
        if s.agent_path not in seen:
            ordered_paths.append(s.agent_path)
            seen.add(s.agent_path)
    for s in prev.steps:
        if s.agent_path not in seen:
            ordered_paths.append(s.agent_path)
            seen.add(s.agent_path)

    deltas: list[TraceStepDelta] = []
    for path in ordered_paths:
        a = prev_by_path.get(path, [])
        b = next_by_path.get(path, [])
        for i in range(max(len(a), len(b))):
            pa = a[i] if i < len(a) else None
            pb = b[i] if i < len(b) else None
            deltas.append(
                _pair_delta(path, pa, pb, latency_tolerance_ms)
            )

    return TraceDiff(
        prev_run_id=prev.run_id,
        next_run_id=next.run_id,
        prev_hash_graph=prev_hash_graph,
        next_hash_graph=next_hash_graph,
        graphs_match=(prev_hash_graph == next_hash_graph),
        steps=deltas,
    )


def _trace_hash_graph(t: Trace) -> str:
    for s in t.steps:
        h = getattr(s.output, "hash_graph", "") or ""
        if h:
            return h
    return ""


def _pair_delta(
    path: str,
    a: TraceStep | None,
    b: TraceStep | None,
    latency_tolerance_ms: float,
) -> TraceStepDelta:
    if a is None and b is not None:
        return TraceStepDelta(
            agent_path=path,
            status="added",
            next_hash_prompt=_h(b, "hash_prompt"),
            next_hash_input=_h(b, "hash_input"),
            next_latency_ms=_lat(b),
            next_response_dump=_dump(b),
            next_error=b.error,
        )
    if b is None and a is not None:
        return TraceStepDelta(
            agent_path=path,
            status="removed",
            prev_hash_prompt=_h(a, "hash_prompt"),
            prev_hash_input=_h(a, "hash_input"),
            prev_latency_ms=_lat(a),
            prev_response_dump=_dump(a),
            prev_error=a.error,
        )
    assert a is not None and b is not None

    reasons: list[str] = []
    a_err, b_err = a.error, b.error
    if a_err or b_err:
        if a_err != b_err:
            reasons.append("error differs")
    else:
        ap = _h(a, "hash_prompt")
        bp = _h(b, "hash_prompt")
        if ap != bp:
            reasons.append("prompt hash diff")
        ai = _h(a, "hash_input")
        bi = _h(b, "hash_input")
        if ai != bi:
            reasons.append("input hash diff")
    da = _lat(a)
    db = _lat(b)
    if abs(db - da) > latency_tolerance_ms:
        sign = "+" if db >= da else ""
        reasons.append(f"latency {sign}{db - da:.1f}ms")

    status: StepStatus = "changed" if reasons else "unchanged"
    return TraceStepDelta(
        agent_path=path,
        status=status,
        prev_hash_prompt=_h(a, "hash_prompt"),
        next_hash_prompt=_h(b, "hash_prompt"),
        prev_hash_input=_h(a, "hash_input"),
        next_hash_input=_h(b, "hash_input"),
        prev_latency_ms=da,
        next_latency_ms=db,
        prev_response_dump=_dump(a),
        next_response_dump=_dump(b),
        prev_error=a_err,
        next_error=b_err,
        reasons=reasons,
    )


def _h(step: TraceStep, field: str) -> str:
    return getattr(step.output, field, "") or ""


def _lat(step: TraceStep) -> float:
    return float(getattr(step.output, "latency_ms", 0.0) or 0.0)


def _dump(step: TraceStep) -> dict[str, Any]:
    resp = getattr(step.output, "response", None)
    if resp is None:
        return {}
    try:
        return resp.model_dump(mode="json")
    except Exception:
        return {}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


__all__ = ["TraceDiff", "TraceStepDelta", "trace_diff"]
