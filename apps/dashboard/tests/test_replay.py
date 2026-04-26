"""Replay JSONL traces through a WebDashboardObserver."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from operad_dashboard.observer import WebDashboardObserver
from operad_dashboard.replay import (
    load_records,
    record_to_envelope,
    replay_file,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _agent_record(run_id: str, kind: str, ts: float) -> dict:
    return {
        "event": "agent",
        "run_id": run_id,
        "agent_path": "Sequential",
        "kind": kind,
        "input": None,
        "output": None,
        "started_at": ts,
        "finished_at": ts + 0.1,
        "metadata": {"is_root": True},
    }


def _algo_record(run_id: str, ts: float) -> dict:
    return {
        "event": "algorithm",
        "run_id": run_id,
        "algorithm_path": "Evolutionary",
        "kind": "generation",
        "payload": {"gen_index": 0},
        "started_at": ts,
        "finished_at": None,
        "metadata": {},
    }


def test_record_to_envelope_unknown_event_returns_none() -> None:
    assert record_to_envelope({"event": "nope"}) is None


def test_load_records_skips_blank_and_invalid_lines(tmp_path: Path) -> None:
    p = tmp_path / "trace.jsonl"
    p.write_text(
        json.dumps(_agent_record("r1", "start", 1.0)) + "\n"
        "\n"
        "{not-json}\n"
        + json.dumps(_agent_record("r1", "end", 2.0)) + "\n",
        encoding="utf-8",
    )
    recs = list(load_records(p))
    assert len(recs) == 2
    assert recs[0]["kind"] == "start"
    assert recs[1]["kind"] == "end"


async def test_replay_file_speed_zero_is_fast(tmp_path: Path) -> None:
    p = tmp_path / "trace.jsonl"
    _write_jsonl(
        p,
        [
            _agent_record("r1", "start", 100.0),
            _algo_record("r1", 100.5),
            _agent_record("r1", "end", 200.0),
        ],
    )
    obs = WebDashboardObserver()
    q = obs.subscribe()
    count = await asyncio.wait_for(replay_file(p, obs, speed=0), timeout=1.0)
    assert count == 3
    items = [q.get_nowait() for _ in range(3)]
    types = [it["type"] for it in items]
    assert types == ["agent_event", "algo_event", "agent_event"]
    assert obs.registry.get("r1").state == "ended"
