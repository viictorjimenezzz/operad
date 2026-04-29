"""Compatibility helpers for OPRO sessions split across step() calls."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .runs import RunInfo, RunRegistry


OPRO_PATHS = {"OPRO", "OPROOptimizer"}


@dataclass(frozen=True)
class OPROSession:
    canonical_run_id: str
    members: tuple[RunInfo, ...]


def is_opro_path(path: str | None) -> bool:
    return path in OPRO_PATHS


def is_opro_run(info: RunInfo) -> bool:
    return is_opro_path(info.algorithm_path)


def build_opro_sessions(runs: Iterable[RunInfo]) -> list[OPROSession]:
    candidates = [run for run in runs if is_opro_run(run)]
    buckets: dict[tuple[str, str], list[RunInfo]] = {}
    for run in candidates:
        key = (run.algorithm_path or "OPRO", _param_key(run))
        buckets.setdefault(key, []).append(run)

    sessions: list[OPROSession] = []
    for members in buckets.values():
        members.sort(key=lambda run: (_first_step(run), run.started_at))
        current: list[RunInfo] = []
        last_step: int | None = None
        for run in members:
            first = _first_step(run)
            last = _last_step(run)
            if current and first is not None and last_step is not None and first == last_step + 1:
                current.append(run)
            else:
                if current:
                    sessions.append(_session(current))
                current = [run]
            last_step = last if last is not None else last_step
        if current:
            sessions.append(_session(current))

    sessions.sort(key=lambda session: session.members[-1].last_event_at, reverse=True)
    return sessions


def find_opro_session(registry: RunRegistry, run_id: str) -> OPROSession | None:
    for session in build_opro_sessions(registry.list()):
        if session.canonical_run_id == run_id:
            return session
    return None


def merged_opro_summary(
    session: OPROSession,
    *,
    cost_totals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    first = session.members[0]
    summary = deepcopy(first.summary())
    members = session.members

    summary["run_id"] = session.canonical_run_id
    summary["started_at"] = min(run.started_at for run in members)
    summary["last_event_at"] = max(run.last_event_at for run in members)
    summary["state"] = _merged_state(members)
    summary["event_counts"] = _sum_event_counts(members)
    summary["event_total"] = sum(summary["event_counts"].values())
    summary["duration_ms"] = max(
        0.0,
        (float(summary["last_event_at"]) - float(summary["started_at"])) * 1000.0,
    )
    summary["algorithm_kinds"] = sorted(
        {kind for run in members for kind in run.algorithm_kinds}
    )
    summary["generations"] = _merge_lists(members, "generations")
    summary["iterations"] = _merge_lists(members, "iterations")
    summary["rounds"] = _merge_lists(members, "rounds")
    summary["candidates"] = _merge_lists(members, "candidates")
    summary["batches"] = _merge_lists(members, "batches")
    summary["prompt_tokens"] = sum(run.total_prompt_tokens for run in members)
    summary["completion_tokens"] = sum(run.total_completion_tokens for run in members)
    summary["metrics"] = _merge_metrics(members)
    summary["parameter_snapshots"] = _merge_lists(members, "parameter_snapshots")
    summary["tape_entries"] = _merge_lists(members, "tape_entries")
    summary["algorithm_terminal_score"] = _merged_terminal_score(members)
    summary["error"] = next((run.error_message for run in reversed(members) if run.error_message), None)

    if cost_totals is not None:
        summary["cost"] = _merged_cost(session, cost_totals)
    return summary


def merged_opro_events(session: OPROSession) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for run in session.members:
        for event in run.events:
            copied = deepcopy(event)
            copied["run_id"] = session.canonical_run_id
            metadata = copied.get("metadata")
            if isinstance(metadata, dict) and metadata.get("parent_run_id") in {
                member.run_id for member in session.members
            }:
                metadata["parent_run_id"] = session.canonical_run_id
            events.append(copied)
    events.sort(key=lambda event: float(event.get("started_at") or 0.0))
    return events


def merged_opro_children(registry: RunRegistry, session: OPROSession) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for run in session.members:
        for child in registry.list_children(run.run_id):
            summary = deepcopy(child.summary())
            summary["parent_run_id"] = session.canonical_run_id
            children.append(summary)
    children.sort(key=lambda child: float(child.get("started_at") or 0.0))
    return children


def _session(members: list[RunInfo]) -> OPROSession:
    members.sort(key=lambda run: run.started_at)
    return OPROSession(canonical_run_id=members[0].run_id, members=tuple(members))


def _param_key(run: RunInfo) -> str:
    paths: set[str] = set()
    for item in run.iterations:
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            path = metadata.get("param_path")
            if isinstance(path, str) and path:
                paths.add(path)
    for event in run.events:
        if event.get("type") != "algo_event" or event.get("kind") != "algo_start":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        raw = payload.get("params")
        if isinstance(raw, list):
            paths.update(str(item) for item in raw if str(item))
    return ",".join(sorted(paths))


def _step_values(run: RunInfo) -> list[int]:
    values: list[int] = []
    for item in run.iterations:
        metadata = item.get("metadata")
        raw = metadata.get("step_index") if isinstance(metadata, dict) else None
        if not isinstance(raw, int):
            raw = item.get("iter_index")
        if isinstance(raw, int):
            values.append(raw)
    return values


def _first_step(run: RunInfo) -> int | None:
    values = _step_values(run)
    return min(values) if values else None


def _last_step(run: RunInfo) -> int | None:
    values = _step_values(run)
    return max(values) if values else None


def _merged_state(members: tuple[RunInfo, ...]) -> str:
    if any(run.state == "error" for run in members):
        return "error"
    if any(run.state == "running" for run in members):
        return "running"
    return "ended"


def _sum_event_counts(members: tuple[RunInfo, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in members:
        for kind, value in run.event_counts.items():
            counts[kind] = counts.get(kind, 0) + value
    return counts


def _merge_lists(members: tuple[RunInfo, ...], attr: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for run in members:
        raw_items = getattr(run, attr)
        items.extend(deepcopy(item) for item in raw_items)
    items.sort(key=lambda item: float(item.get("timestamp") or 0.0))
    return items


def _merge_metrics(members: tuple[RunInfo, ...]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for run in sorted(members, key=lambda item: item.started_at):
        metrics.update(run.metrics)
    return metrics


def _merged_terminal_score(members: tuple[RunInfo, ...]) -> float | None:
    values = [
        run.algorithm_terminal_score
        for run in members
        if run.algorithm_terminal_score is not None
    ]
    return values[-1] if values else None


def _merged_cost(session: OPROSession, cost_totals: dict[str, Any]) -> dict[str, float]:
    total = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "cost_usd": 0.0}
    for run in session.members:
        item = cost_totals.get(run.run_id)
        if not isinstance(item, dict):
            continue
        for key in total:
            value = item.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total[key] += float(value)
    return {
        "prompt_tokens": int(total["prompt_tokens"]),
        "completion_tokens": int(total["completion_tokens"]),
        "cost_usd": total["cost_usd"],
    }
