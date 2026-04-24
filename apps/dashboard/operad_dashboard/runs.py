"""In-memory ring buffer of recent operad runs.

Each `RunInfo` carries the rolling window of event envelopes for the run
plus aggregated per-run state the UI needs: event counts by kind,
generation payloads (for evolutionary runs), cached Mermaid graph,
and running token totals. The registry is bounded; oldest runs drop
out via `OrderedDict.popitem(last=False)`.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Literal

from operad.core.graph import TypeRegistry, from_json, to_mermaid


RunState = Literal["running", "ended", "error"]

_DEFAULT_CAPACITY = 100
_DEFAULT_EVENT_WINDOW = 500


@dataclass
class RunInfo:
    run_id: str
    started_at: float
    last_event_at: float
    state: RunState = "running"
    mermaid: str | None = None
    events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=_DEFAULT_EVENT_WINDOW)
    )
    event_counts: dict[str, int] = field(default_factory=dict)
    algorithm_path: str | None = None
    algorithm_kinds: set[str] = field(default_factory=set)
    generations: list[dict[str, Any]] = field(default_factory=list)
    iterations: list[dict[str, Any]] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    batches: list[dict[str, Any]] = field(default_factory=list)
    root_agent_path: str | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    error_message: str | None = None
    algorithm_terminal_score: float | None = None

    @property
    def is_algorithm(self) -> bool:
        return self.algorithm_path is not None

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.last_event_at - self.started_at) * 1000.0)

    @property
    def event_total(self) -> int:
        return sum(self.event_counts.values())

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "last_event_at": self.last_event_at,
            "state": self.state,
            "has_graph": self.mermaid is not None,
            "is_algorithm": self.is_algorithm,
            "algorithm_path": self.algorithm_path,
            "algorithm_kinds": sorted(self.algorithm_kinds),
            "root_agent_path": self.root_agent_path,
            "event_counts": dict(self.event_counts),
            "event_total": self.event_total,
            "duration_ms": self.duration_ms,
            "generations": list(self.generations),
            "iterations": list(self.iterations),
            "rounds": list(self.rounds),
            "candidates": list(self.candidates),
            "batches": list(self.batches),
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "error": self.error_message,
            "algorithm_terminal_score": self.algorithm_terminal_score,
        }


class RunRegistry:
    """Bounded LRU of run_id → RunInfo. Drop-oldest on overflow."""

    def __init__(
        self,
        capacity: int = _DEFAULT_CAPACITY,
        event_window: int = _DEFAULT_EVENT_WINDOW,
    ) -> None:
        self._capacity = capacity
        self._event_window = event_window
        self._runs: OrderedDict[str, RunInfo] = OrderedDict()
        self._type_registry = TypeRegistry()

    def __len__(self) -> int:
        return len(self._runs)

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._runs

    def get(self, run_id: str) -> RunInfo | None:
        return self._runs.get(run_id)

    def list(self) -> list[RunInfo]:
        return list(reversed(self._runs.values()))

    def all_generations(self) -> list[dict[str, Any]]:
        """Flatten generation events across all runs, ordered by time."""
        out: list[dict[str, Any]] = []
        for info in self._runs.values():
            for g in info.generations:
                out.append({**g, "run_id": info.run_id, "algorithm_path": info.algorithm_path})
        out.sort(key=lambda g: g.get("timestamp") or 0.0)
        return out

    def global_stats(self) -> dict[str, Any]:
        runs = list(self._runs.values())
        states = {"running": 0, "ended": 0, "error": 0}
        event_total = 0
        prompt_tokens = 0
        completion_tokens = 0
        algo_runs = 0
        agent_runs = 0
        for r in runs:
            states[r.state] = states.get(r.state, 0) + 1
            event_total += r.event_total
            prompt_tokens += r.total_prompt_tokens
            completion_tokens += r.total_completion_tokens
            if r.is_algorithm:
                algo_runs += 1
            elif r.root_agent_path is not None:
                agent_runs += 1
        return {
            "runs_total": len(runs),
            "runs_running": states["running"],
            "runs_ended": states["ended"],
            "runs_error": states["error"],
            "runs_algorithm": algo_runs,
            "runs_agent": agent_runs,
            "event_total": event_total,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    def record_envelope(self, envelope: dict[str, Any]) -> None:
        """Absorb one SSE envelope into the per-run state."""
        run_id = envelope.get("run_id") or ""
        if not run_id:
            return
        ts_raw = envelope.get("started_at")
        ts = float(ts_raw) if isinstance(ts_raw, (int, float)) else time.time()
        info = self._ensure(run_id, ts)
        info.events.append(envelope)
        env_type = envelope.get("type")
        kind = envelope.get("kind") or "unknown"
        info.event_counts[kind] = info.event_counts.get(kind, 0) + 1
        if ts > info.last_event_at:
            info.last_event_at = ts

        if env_type == "algo_event":
            self._record_algo(info, envelope, kind)
        elif env_type == "agent_event":
            self._record_agent(info, envelope, kind)

    def _ensure(self, run_id: str, ts: float) -> RunInfo:
        info = self._runs.get(run_id)
        if info is None:
            info = RunInfo(
                run_id=run_id,
                started_at=ts,
                last_event_at=ts,
                events=deque(maxlen=self._event_window),
            )
            self._runs[run_id] = info
            self._evict_if_needed()
        else:
            self._runs.move_to_end(run_id)
        return info

    def _record_algo(
        self, info: RunInfo, envelope: dict[str, Any], kind: str
    ) -> None:
        algo_path = envelope.get("algorithm_path")
        if algo_path:
            info.algorithm_path = algo_path
        info.algorithm_kinds.add(kind)
        payload = envelope.get("payload") or {}
        ts = envelope.get("started_at")
        if kind == "generation":
            scores = payload.get("population_scores") or []
            best = max(scores) if scores else None
            mean = sum(scores) / len(scores) if scores else None
            info.generations.append(
                {
                    "gen_index": payload.get("gen_index"),
                    "best": best,
                    "mean": mean,
                    "scores": list(scores),
                    "survivor_indices": list(payload.get("survivor_indices") or []),
                    "op_attempt_counts": dict(payload.get("op_attempt_counts") or {}),
                    "op_success_counts": dict(payload.get("op_success_counts") or {}),
                    "timestamp": ts,
                }
            )
        elif kind == "iteration":
            info.iterations.append(
                {
                    "iter_index": payload.get("iter_index"),
                    "phase": payload.get("phase"),
                    "score": payload.get("score"),
                    "timestamp": ts,
                }
            )
        elif kind == "round":
            info.rounds.append(
                {
                    "round_index": payload.get("round_index"),
                    "scores": list(payload.get("scores") or []),
                    "timestamp": ts,
                }
            )
        elif kind == "candidate":
            info.candidates.append(
                {
                    "candidate_index": payload.get("candidate_index"),
                    "score": payload.get("score"),
                    "timestamp": ts,
                }
            )
        elif kind in {"batch_start", "batch_end"}:
            info.batches.append(
                {
                    "kind": kind,
                    "batch_index": payload.get("batch_index"),
                    "batch_size": payload.get("batch_size"),
                    "duration_ms": payload.get("duration_ms"),
                    "epoch": payload.get("epoch"),
                    "timestamp": ts,
                }
            )
        elif kind == "algo_end":
            info.state = "ended"
            score = payload.get("score")
            if isinstance(score, (int, float)):
                info.algorithm_terminal_score = float(score)
        elif kind == "algo_error":
            info.state = "error"
            info.error_message = str(payload.get("message") or "")

    def _record_agent(
        self, info: RunInfo, envelope: dict[str, Any], kind: str
    ) -> None:
        metadata = envelope.get("metadata") or {}
        is_root = bool(metadata.get("is_root"))
        agent_path = envelope.get("agent_path")
        if is_root and agent_path:
            info.root_agent_path = agent_path
            if kind == "end":
                info.state = "ended"
            elif kind == "error":
                info.state = "error"
                err = envelope.get("error") or {}
                info.error_message = (
                    f"{err.get('type') or 'Error'}: {err.get('message') or ''}".strip()
                )
        if info.mermaid is None:
            graph_data = metadata.get("graph")
            if isinstance(graph_data, dict) and graph_data.get("nodes"):
                info.mermaid = self._render_mermaid(graph_data)
        if kind == "end":
            out = envelope.get("output")
            if isinstance(out, dict):
                p = out.get("prompt_tokens")
                c = out.get("completion_tokens")
                if isinstance(p, int):
                    info.total_prompt_tokens += p
                if isinstance(c, int):
                    info.total_completion_tokens += c

    # --- legacy facade kept so replay.py + tests continue to work ----

    def observe_agent_event(
        self,
        *,
        run_id: str,
        kind: str,
        timestamp: float,
        metadata: dict[str, Any] | None,
    ) -> None:
        info = self._ensure(run_id, timestamp)
        if timestamp > info.last_event_at:
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
        info = self._ensure(run_id, timestamp)
        if timestamp > info.last_event_at:
            info.last_event_at = timestamp

    def _render_mermaid(self, graph_data: dict[str, Any]) -> str:
        try:
            graph = from_json(graph_data, self._type_registry)
            return to_mermaid(graph)
        except Exception:
            return _fallback_mermaid(graph_data)

    def _evict_if_needed(self) -> None:
        while len(self._runs) > self._capacity:
            self._runs.popitem(last=False)


def _fallback_mermaid(graph_data: dict[str, Any]) -> str:
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
