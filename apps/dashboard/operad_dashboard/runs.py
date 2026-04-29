"""In-memory ring buffer of recent operad runs.

Each `RunInfo` carries the rolling window of event envelopes for the run
plus aggregated per-run state the UI needs: event counts by kind,
generation payloads (for evolutionary runs), cached Mermaid graph,
and running token totals. The registry is bounded; oldest runs drop
out via `OrderedDict.popitem(last=False)`.

Synthetic runs
--------------
When an algorithm orchestrates many inner agent invocations (e.g.
EvoGradient running 96 candidates), each inner invocation emits its own
``run_id`` but carries ``metadata.parent_run_id`` pointing at the
algorithm's top-level run. The registry marks those as *synthetic*
(``RunInfo.synthetic = True``) and links them via ``parent_run_id``.

``GET /runs`` hides synthetic runs by default; pass ``?include=synthetic``
to see them. Use ``GET /runs/{id}/children`` to enumerate the synthetic
children of an algorithm run, and ``GET /runs/{id}/tree`` for the full
subtree in one call.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Iterator, Literal

from operad.core.view import TypeRegistry, from_json, to_mermaid


RunState = Literal["running", "ended", "error"]

_DEFAULT_CAPACITY = 100
_DEFAULT_EVENTS_PER_RUN = 1000


@dataclass
class RunInfo:
    run_id: str
    started_at: float
    last_event_at: float
    state: RunState = "running"
    mermaid: str | None = None
    graph_json: dict[str, Any] | None = None
    events: Deque[dict[str, Any]] = field(default_factory=deque)
    events_by_agent_path: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    event_counts: dict[str, int] = field(default_factory=dict)
    algorithm_path: str | None = None
    algorithm_kinds: set[str] = field(default_factory=set)
    generations: list[dict[str, Any]] = field(default_factory=list)
    iterations: list[dict[str, Any]] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    batches: list[dict[str, Any]] = field(default_factory=list)
    root_agent_path: str | None = None
    script: str | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    notes_markdown: str = ""
    parameter_snapshots: list[dict[str, Any]] = field(default_factory=list)
    tape_entries: list[dict[str, Any]] = field(default_factory=list)
    traceback_path: str | None = None
    error_message: str | None = None
    algorithm_terminal_score: float | None = None
    parent_run_id: str | None = None
    synthetic: bool = False

    @property
    def algorithm_class(self) -> str | None:
        if self.algorithm_path is None:
            return None
        return self.algorithm_path.rsplit(".", 1)[-1]

    @property
    def is_algorithm(self) -> bool:
        return self.algorithm_path is not None

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.last_event_at - self.started_at) * 1000.0)

    @property
    def event_total(self) -> int:
        return sum(self.event_counts.values())

    def latest_parameter_snapshot(self) -> dict[str, Any]:
        for snapshot in reversed(self.parameter_snapshots):
            values = snapshot.get("values")
            if isinstance(values, dict) and values:
                return dict(values)
        return {}

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "last_event_at": self.last_event_at,
            "state": self.state,
            "has_graph": self.mermaid is not None,
            "graph_json": self.graph_json,
            "is_algorithm": self.is_algorithm,
            "algorithm_path": self.algorithm_path,
            "algorithm_kinds": sorted(self.algorithm_kinds),
            "root_agent_path": self.root_agent_path,
            "script": self.script,
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
            "metrics": dict(self.metrics),
            "notes_markdown": self.notes_markdown,
            "parameter_snapshots": list(self.parameter_snapshots),
            "tape_entries": list(self.tape_entries),
            "traceback_path": self.traceback_path,
            "has_traceback": self.traceback_path is not None,
            "error": self.error_message,
            "algorithm_terminal_score": self.algorithm_terminal_score,
            "parent_run_id": self.parent_run_id,
            "synthetic": self.synthetic,
            "algorithm_class": self.algorithm_class,
        }


class RunRegistry:
    """Bounded LRU of run_id → RunInfo. Drop-oldest on overflow.

    Each RunInfo also holds a bounded deque of already-serialized event
    envelopes so per-run dashboard panels can reconstruct historical state
    on page load without touching the live SSE stream.
    """

    def __init__(
        self,
        capacity: int = _DEFAULT_CAPACITY,
        *,
        events_per_run: int = _DEFAULT_EVENTS_PER_RUN,
    ) -> None:
        self._capacity = capacity
        self._events_per_run = events_per_run
        self._runs: OrderedDict[str, RunInfo] = OrderedDict()
        self._type_registry = TypeRegistry()

    def _new_run_info(self, run_id: str, timestamp: float) -> RunInfo:
        return RunInfo(
            run_id=run_id,
            started_at=timestamp,
            last_event_at=timestamp,
            events=deque(maxlen=self._events_per_run),
        )

    def __len__(self) -> int:
        return len(self._runs)

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._runs

    def get(self, run_id: str) -> RunInfo | None:
        return self._runs.get(run_id)

    def list(self) -> list[RunInfo]:
        # Newest first.
        return list(reversed(self._runs.values()))

    def list_children(self, parent_run_id: str) -> list[RunInfo]:
        return [r for r in self._runs.values() if r.parent_run_id == parent_run_id]

    def runs_by_hash_full(self, hash_content: str) -> list[RunInfo]:
        target = hash_content.strip()
        matches = [
            r for r in self._runs.values()
            if _latest_hash_content(r) == target
        ]
        matches.sort(key=lambda r: r.started_at)
        return matches

    def clear(self) -> None:
        self._runs.clear()

    def restore_snapshot(
        self,
        *,
        summary: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> RunInfo:
        run_id = str(summary.get("run_id") or "")
        if not run_id:
            raise ValueError("summary missing run_id")
        started_at = float(summary.get("started_at") or time.time())
        info = self._new_run_info(run_id, started_at)
        info.last_event_at = float(summary.get("last_event_at") or started_at)
        info.state = summary.get("state") or "running"
        info.mermaid = None
        info.graph_json = summary.get("graph_json") if isinstance(summary.get("graph_json"), dict) else None
        info.algorithm_path = summary.get("algorithm_path")
        info.algorithm_kinds = set(summary.get("algorithm_kinds") or [])
        info.generations = list(summary.get("generations") or [])
        info.iterations = list(summary.get("iterations") or [])
        info.rounds = list(summary.get("rounds") or [])
        info.candidates = list(summary.get("candidates") or [])
        info.batches = list(summary.get("batches") or [])
        info.root_agent_path = summary.get("root_agent_path")
        info.script = summary.get("script")
        info.total_prompt_tokens = int(summary.get("prompt_tokens") or 0)
        info.total_completion_tokens = int(summary.get("completion_tokens") or 0)
        metrics = summary.get("metrics")
        if isinstance(metrics, dict):
            info.metrics = {
                str(k): float(v)
                for k, v in metrics.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
        notes = summary.get("notes_markdown")
        info.notes_markdown = notes if isinstance(notes, str) else ""
        snapshots = summary.get("parameter_snapshots")
        info.parameter_snapshots = (
            [s for s in snapshots if isinstance(s, dict)]
            if isinstance(snapshots, list)
            else []
        )
        tape_entries = summary.get("tape_entries")
        info.tape_entries = (
            [entry for entry in tape_entries if isinstance(entry, dict)]
            if isinstance(tape_entries, list)
            else []
        )
        traceback_path = summary.get("traceback_path")
        info.traceback_path = (
            traceback_path
            if isinstance(traceback_path, str) and traceback_path
            else None
        )
        info.error_message = summary.get("error")
        score = summary.get("algorithm_terminal_score")
        info.algorithm_terminal_score = float(score) if isinstance(score, (int, float)) else None
        info.parent_run_id = summary.get("parent_run_id")
        info.synthetic = bool(summary.get("synthetic"))
        info.event_counts = dict(summary.get("event_counts") or {})
        info.events.clear()
        info.events_by_agent_path.clear()
        for envelope in events:
            info.events.append(envelope)
            self._index_event_by_agent_path(info, envelope)
            if info.mermaid is None and envelope.get("type") == "graph_envelope":
                mermaid = envelope.get("mermaid")
                if isinstance(mermaid, str):
                    info.mermaid = mermaid
        self._runs[run_id] = info
        self._runs.move_to_end(run_id)
        self._evict_if_needed()
        return info

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
        """Absorb one SSE envelope: append to history + update aggregated state."""
        run_id = envelope.get("run_id") or ""
        if not run_id:
            return
        ts_raw = envelope.get("started_at")
        ts = float(ts_raw) if isinstance(ts_raw, (int, float)) else time.time()
        is_new = run_id not in self._runs
        info = self._ensure(run_id, ts)
        if is_new:
            meta = envelope.get("metadata") or {}
            parent = meta.get("parent_run_id")
            if isinstance(parent, str) and parent:
                info.parent_run_id = parent
                info.synthetic = True
        info.events.append(envelope)
        self._index_event_by_agent_path(info, envelope)
        env_type = envelope.get("type")
        kind = envelope.get("kind") or "unknown"
        info.event_counts[kind] = info.event_counts.get(kind, 0) + 1
        if ts > info.last_event_at:
            info.last_event_at = ts
        self._record_metrics(info, envelope)

        if env_type == "algo_event":
            self._record_algo(info, envelope, kind)
        elif env_type == "agent_event":
            self._record_agent(info, envelope, kind)

    def append_event(self, run_id: str, envelope: dict[str, Any]) -> None:
        """Legacy: append a serialized envelope to a run's history buffer.

        Kept for back-compat with routes that call this directly; delegates
        to `record_envelope` so aggregated state stays in sync.
        """
        if envelope.get("run_id") != run_id:
            envelope = {**envelope, "run_id": run_id}
        self.record_envelope(envelope)

    def iter_events(
        self,
        run_id: str,
        *,
        event_type: str | None = None,
        kind: str | tuple[str, ...] | None = None,
        algorithm_path: str | tuple[str, ...] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield buffered envelopes for a run, filtered by optional fields.

        `event_type` matches the envelope `"type"` (e.g. `"algo_event"`).
        `kind` matches the envelope `"kind"`; tuple = any-of.
        `algorithm_path` matches `"algorithm_path"` on algo envelopes; tuple = any-of.
        """
        info = self._runs.get(run_id)
        if info is None:
            return
        kinds = _as_tuple(kind)
        algos = _as_tuple(algorithm_path)
        for env in info.events:
            if event_type is not None and env.get("type") != event_type:
                continue
            if kinds and env.get("kind") not in kinds:
                continue
            if algos and env.get("algorithm_path") not in algos:
                continue
            yield env

    def _ensure(self, run_id: str, ts: float) -> RunInfo:
        info = self._runs.get(run_id)
        if info is None:
            info = self._new_run_info(run_id, ts)
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
        if kind == "algo_start":
            mermaid = payload.get("graph_mermaid")
            if isinstance(mermaid, str) and info.mermaid is None:
                info.mermaid = mermaid
            graph_json = payload.get("graph_json")
            if isinstance(graph_json, dict) and info.graph_json is None:
                info.graph_json = graph_json
            root_path = payload.get("root_path")
            if isinstance(root_path, str) and info.root_agent_path is None:
                info.root_agent_path = root_path
        elif kind == "generation":
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
                    "selected_lineage_id": payload.get("selected_lineage_id"),
                    "individuals": list(payload.get("individuals") or []),
                    "op_attempt_counts": dict(payload.get("op_attempt_counts") or {}),
                    "op_success_counts": dict(payload.get("op_success_counts") or {}),
                    "timestamp": ts,
                }
            )
        elif kind == "iteration":
            metadata = {
                k: v
                for k, v in payload.items()
                if k not in {"iter_index", "phase", "score", "text"}
            }
            parameter_snapshot = payload.get("parameter_snapshot")
            if payload.get("phase") == "epoch_end" and isinstance(
                parameter_snapshot, dict
            ):
                context = _snapshot_context(payload)
                info.parameter_snapshots.append(
                    {
                        "source": "epoch_end",
                        "epoch": payload.get("epoch"),
                        "values": dict(parameter_snapshot),
                        "timestamp": ts,
                        "tape_link": context,
                    }
                )
            traceback_path = payload.get("path")
            if (
                payload.get("phase") == "traceback"
                and isinstance(traceback_path, str)
                and traceback_path
            ):
                info.traceback_path = traceback_path
            info.iterations.append(
                {
                    "iter_index": payload.get("iter_index"),
                    "phase": payload.get("phase"),
                    "score": payload.get("score"),
                    "text": payload.get("text"),
                    "metadata": metadata,
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
                    "iter_index": payload.get("iter_index"),
                    "candidate_index": payload.get("candidate_index"),
                    "score": payload.get("score"),
                    "text": payload.get("text"),
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
        tape_entry = metadata.get("tape_entry")
        if isinstance(tape_entry, dict):
            info.tape_entries.append(dict(tape_entry))
        is_root = bool(metadata.get("is_root"))
        agent_path = envelope.get("agent_path")
        if is_root and agent_path:
            info.root_agent_path = agent_path
            script = metadata.get("script")
            if isinstance(script, str) and info.script is None:
                info.script = script
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
                info.graph_json = graph_data
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
        if kind == "end":
            params = metadata.get("parameters")
            if isinstance(params, list):
                values: dict[str, Any] = {}
                details: dict[str, dict[str, Any]] = {}
                for raw in params:
                    if not isinstance(raw, dict):
                        continue
                    if not raw.get("requires_grad"):
                        continue
                    path = raw.get("path")
                    if isinstance(path, str) and path:
                        values[path] = raw.get("value")
                        detail: dict[str, Any] = {
                            "requires_grad": True,
                        }
                        hv = raw.get("hash")
                        if isinstance(hv, str) and hv:
                            detail["hash"] = hv
                        tape_link = _normalize_tape_link(raw.get("tape_link"))
                        if tape_link is not None:
                            detail["tape_link"] = tape_link
                        gradient = _normalize_gradient(raw.get("gradient") or raw.get("grad"))
                        if gradient is not None:
                            detail["gradient"] = gradient
                        details[path] = detail
                if values:
                    info.parameter_snapshots.append(
                        {
                            "source": "agent_event",
                            "agent_path": agent_path,
                            "values": values,
                            "details": details,
                            "timestamp": envelope.get("finished_at")
                            or envelope.get("started_at"),
                        }
                    )

    # --- legacy facade kept so existing callers continue to work ------

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
                info.graph_json = graph_data
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

    def _index_event_by_agent_path(
        self, info: RunInfo, envelope: dict[str, Any]
    ) -> None:
        path = envelope.get("agent_path")
        if isinstance(path, str) and path:
            info.events_by_agent_path.setdefault(path, []).append(envelope)

    def _record_metrics(self, info: RunInfo, envelope: dict[str, Any]) -> None:
        metadata = envelope.get("metadata")
        if not isinstance(metadata, dict):
            return
        metrics = metadata.get("metrics")
        if not isinstance(metrics, dict):
            return
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                info.metrics[str(name)] = float(value)

    def _evict_if_needed(self) -> None:
        while len(self._runs) > self._capacity:
            self._runs.popitem(last=False)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _snapshot_context(payload: dict[str, Any]) -> dict[str, int] | None:
    tape = _normalize_tape_link(payload)
    if tape is not None:
        return tape
    return None


def _normalize_tape_link(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    mapping = {
        "epoch": "epoch",
        "batch": "batch",
        "iter": "iter",
        "optimizer_step": "optimizer_step",
        "optimizerStep": "optimizer_step",
    }
    for src, dst in mapping.items():
        value = raw.get(src)
        if isinstance(value, int):
            out[dst] = value
        elif isinstance(value, float):
            out[dst] = int(value)
    return out or None


def _normalize_gradient(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    message = raw.get("message")
    if isinstance(message, str):
        out["message"] = message
    severity = raw.get("severity")
    if isinstance(severity, (int, float, str)):
        out["severity"] = severity
    target_paths = raw.get("target_paths")
    if isinstance(target_paths, list):
        out["target_paths"] = [str(item) for item in target_paths if isinstance(item, str)]
    return out or None


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


def _latest_hash_content(info: RunInfo) -> str | None:
    root = info.root_agent_path
    for env in reversed(list(info.events)):
        if env.get("type") != "agent_event":
            continue
        if env.get("kind") not in {"end", "start"}:
            continue
        if isinstance(root, str) and env.get("agent_path") != root:
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        hc = meta.get("hash_content")
        if isinstance(hc, str) and hc:
            return hc
    return None
