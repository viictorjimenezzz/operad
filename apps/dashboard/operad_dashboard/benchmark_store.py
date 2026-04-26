"""In-memory store for benchmark reports consumed by dashboard `/benchmarks` routes."""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class BenchmarkMeta:
    id: str
    name: str
    created_at: float
    tag: str | None
    tagged_at: float | None
    n_tasks: int
    n_methods: int


@dataclass
class BenchmarkEntry:
    meta: BenchmarkMeta
    report: dict[str, Any]


class BenchmarkStore:
    def __init__(self) -> None:
        self._entries: dict[str, BenchmarkEntry] = {}
        self._order: list[str] = []

    def ingest(self, raw_report: Any) -> str:
        report = _validate_report(raw_report)
        bench_id = str(uuid.uuid4())
        now = time.time()
        name = _derive_name(report, bench_id)

        tasks = sorted({str(row["task"]) for row in report["summary"]})
        methods = sorted({str(row["method"]) for row in report["summary"]})

        meta = BenchmarkMeta(
            id=bench_id,
            name=name,
            created_at=now,
            tag=None,
            tagged_at=None,
            n_tasks=len(tasks),
            n_methods=len(methods),
        )
        self._entries[bench_id] = BenchmarkEntry(meta=meta, report=deepcopy(report))
        self._order.insert(0, bench_id)
        return bench_id

    def list(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for bench_id in self._order:
            entry = self._entries.get(bench_id)
            if entry is None:
                continue
            items.append(self._summary_payload(entry))
        return items

    def get(self, bench_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(bench_id)
        if entry is None:
            return None
        return {
            "id": entry.meta.id,
            "name": entry.meta.name,
            "created_at": entry.meta.created_at,
            "tag": entry.meta.tag,
            "tagged_at": entry.meta.tagged_at,
            "n_tasks": entry.meta.n_tasks,
            "n_methods": entry.meta.n_methods,
            "report": deepcopy(entry.report),
        }

    def get_report(self, bench_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(bench_id)
        if entry is None:
            return None
        return deepcopy(entry.report)

    def tag(self, bench_id: str, tag: str) -> bool:
        entry = self._entries.get(bench_id)
        if entry is None:
            return False
        if entry.meta.tag == tag:
            return True
        entry.meta.tag = tag
        entry.meta.tagged_at = time.time()
        return True

    def delete(self, bench_id: str) -> bool:
        if bench_id not in self._entries:
            return False
        del self._entries[bench_id]
        self._order = [rid for rid in self._order if rid != bench_id]
        return True

    def latest_tagged_id(self) -> str | None:
        best_id: str | None = None
        best_time: float = -1.0
        for bench_id in self._order:
            entry = self._entries.get(bench_id)
            if entry is None or entry.meta.tagged_at is None:
                continue
            if entry.meta.tagged_at > best_time:
                best_time = entry.meta.tagged_at
                best_id = bench_id
        return best_id

    def _summary_payload(self, entry: BenchmarkEntry) -> dict[str, Any]:
        return {
            "id": entry.meta.id,
            "name": entry.meta.name,
            "created_at": entry.meta.created_at,
            "tag": entry.meta.tag,
            "tagged_at": entry.meta.tagged_at,
            "n_tasks": entry.meta.n_tasks,
            "n_methods": entry.meta.n_methods,
            "summary": _global_summary(entry.report["summary"]),
            "leaderboard": _task_leaderboard(entry.report["summary"]),
        }


def compute_delta_rows(
    current_report: dict[str, Any],
    baseline_report: dict[str, Any],
) -> list[dict[str, Any]]:
    base = {
        (str(r["task"]), str(r["method"])): float(r["mean"])
        for r in baseline_report.get("summary", [])
    }
    rows: list[dict[str, Any]] = []
    for row in current_report.get("summary", []):
        key = (str(row["task"]), str(row["method"]))
        if key not in base:
            continue
        rows.append(
            {
                "task": key[0],
                "method": key[1],
                "delta": float(row["mean"]) - base[key],
            }
        )
    rows.sort(key=lambda x: (x["task"], x["method"]))
    return rows


def _derive_name(report: dict[str, Any], bench_id: str) -> str:
    metadata = report.get("metadata")
    if isinstance(metadata, dict):
        candidate = metadata.get("name") or metadata.get("title")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return f"benchmark-{bench_id[:8]}"


def _global_summary(summary_rows: list[dict[str, Any]]) -> str:
    if not summary_rows:
        return "no summary"
    best = max(summary_rows, key=lambda r: float(r["mean"]))
    return f"best {best['method']} on {best['task']} ({float(best['mean']):.3f})"


def _task_leaderboard(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for row in summary_rows:
        task = str(row["task"])
        by_task.setdefault(task, []).append(row)

    leaders: list[dict[str, Any]] = []
    for task, rows in sorted(by_task.items()):
        top = max(rows, key=lambda r: float(r["mean"]))
        leaders.append(
            {
                "task": task,
                "method": str(top["method"]),
                "mean": float(top["mean"]),
            }
        )
    return leaders


def _validate_report(raw_report: Any) -> dict[str, Any]:
    if not isinstance(raw_report, dict):
        raise ValueError("report must be a JSON object")

    cells = raw_report.get("cells")
    summary = raw_report.get("summary")
    headline = raw_report.get("headline_findings")

    if not isinstance(cells, list):
        raise ValueError("report.cells must be a list")
    if not isinstance(summary, list):
        raise ValueError("report.summary must be a list")
    if not isinstance(headline, dict):
        raise ValueError("report.headline_findings must be an object")

    norm_cells: list[dict[str, Any]] = []
    for i, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise ValueError(f"report.cells[{i}] must be an object")
        task = _as_str(cell, "task", f"report.cells[{i}]")
        method = _as_str(cell, "method", f"report.cells[{i}]")
        seed = _as_int(cell, "seed", f"report.cells[{i}]")
        metric = _as_str(cell, "metric", f"report.cells[{i}]")
        score = _as_float(cell, "score", f"report.cells[{i}]")
        tokens = cell.get("tokens")
        if not isinstance(tokens, dict):
            raise ValueError(f"report.cells[{i}].tokens must be an object")
        prompt = _as_int(tokens, "prompt", f"report.cells[{i}].tokens")
        completion = _as_int(tokens, "completion", f"report.cells[{i}].tokens")
        latency = _as_float(cell, "latency_s", f"report.cells[{i}]")
        norm_cells.append(
            {
                "task": task,
                "method": method,
                "seed": seed,
                "metric": metric,
                "score": score,
                "tokens": {"prompt": prompt, "completion": completion},
                "latency_s": latency,
            }
        )

    norm_summary: list[dict[str, Any]] = []
    for i, row in enumerate(summary):
        if not isinstance(row, dict):
            raise ValueError(f"report.summary[{i}] must be an object")
        norm_summary.append(
            {
                "task": _as_str(row, "task", f"report.summary[{i}]"),
                "method": _as_str(row, "method", f"report.summary[{i}]"),
                "mean": _as_float(row, "mean", f"report.summary[{i}]"),
                "std": _as_float(row, "std", f"report.summary[{i}]"),
                "tokens_mean": _as_int(row, "tokens_mean", f"report.summary[{i}]"),
                "latency_mean": _as_float(row, "latency_mean", f"report.summary[{i}]"),
                "n": _as_int(row, "n", f"report.summary[{i}]"),
            }
        )

    norm_findings: dict[str, str] = {}
    for k, v in headline.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("report.headline_findings must map string to string")
        norm_findings[k] = v

    return {
        "cells": norm_cells,
        "summary": norm_summary,
        "headline_findings": norm_findings,
    }


def _as_str(obj: dict[str, Any], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}.{key} must be a non-empty string")
    return value


def _as_int(obj: dict[str, Any], key: str, where: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{where}.{key} must be an integer")
    return value


def _as_float(obj: dict[str, Any], key: str, where: str) -> float:
    value = obj.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{where}.{key} must be a number")
    return float(value)


__all__ = ["BenchmarkStore", "compute_delta_rows"]
