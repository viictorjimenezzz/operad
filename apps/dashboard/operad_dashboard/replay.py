"""Replay a JSONL trace (operad ``JsonlObserver`` format) into a WebDashboardObserver."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterator

from .observer import WebDashboardObserver


def load_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield one record per line of a JsonlObserver-format file."""
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def record_to_envelope(record: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a JsonlObserver record into a /stream-style SSE envelope.

    Returns None when the record's `event` discriminator is unknown, so
    forward-compatible record types don't crash the replay.
    """
    kind = record.get("event")
    if kind == "agent":
        meta = dict(record.get("metadata") or {})
        if "graph" in meta:
            meta["graph"] = "<cached at /graph/{run_id}>"
        return {
            "type": "agent_event",
            "run_id": record.get("run_id", ""),
            "agent_path": record.get("agent_path", ""),
            "kind": record.get("kind", ""),
            "input": record.get("input"),
            "output": record.get("output"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "metadata": meta,
            "error": record.get("error"),
        }
    if kind == "algorithm":
        return {
            "type": "algo_event",
            "run_id": record.get("run_id", ""),
            "algorithm_path": record.get("algorithm_path", ""),
            "kind": record.get("kind", ""),
            "payload": record.get("payload") or {},
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "metadata": record.get("metadata") or {},
        }
    return None


async def replay_file(
    path: str | Path,
    observer: WebDashboardObserver,
    *,
    speed: float = 1.0,
) -> int:
    """Replay every record in `path` through `observer`. Returns the count.

    `speed` scales recorded inter-event delays. `speed=0` disables sleep
    (fastest path, used for tests and offline smoke).
    """
    count = 0
    prev_ts: float | None = None
    for record in load_records(path):
        envelope = record_to_envelope(record)
        if envelope is None:
            continue
        if speed > 0:
            ts = record.get("started_at")
            if isinstance(ts, (int, float)) and prev_ts is not None:
                gap = max(0.0, (float(ts) - prev_ts) / speed)
                if gap > 0:
                    await asyncio.sleep(gap)
            if isinstance(ts, (int, float)):
                prev_ts = float(ts)
        await observer.broadcast(envelope)
        count += 1
    return count
