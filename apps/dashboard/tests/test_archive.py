from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver
from operad_dashboard.runs import RunInfo


def _seed_archived_run(
    app,
    *,
    run_id: str,
    started_at: float,
    algorithm_path: str,
) -> None:
    info = RunInfo(
        run_id=run_id,
        started_at=started_at,
        last_event_at=started_at + 1,
        state="ended",
        algorithm_path=algorithm_path,
        events=deque(maxlen=1000),
    )
    info.events.append(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": algorithm_path,
            "kind": "algo_start",
            "payload": {},
            "started_at": started_at,
            "finished_at": None,
            "metadata": {},
        }
    )
    info.events.append(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": algorithm_path,
            "kind": "algo_end",
            "payload": {"score": 0.7},
            "started_at": started_at + 1,
            "finished_at": started_at + 1,
            "metadata": {},
        }
    )
    info.event_counts = {"algo_start": 1, "algo_end": 1}
    app.state.archive_store.upsert_snapshot(info)


def _wait_for_archive(app, run_id: str, timeout_s: float = 2.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = app.state.archive_store.list_runs(limit=200)
        if any(row["run_id"] == run_id for row in rows):
            return
        time.sleep(0.02)
    raise AssertionError(f"run_id {run_id!r} not archived within timeout")


@pytest.fixture
def app_and_obs(tmp_path: Path):
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False, data_dir=tmp_path)
    return app, obs


def test_archive_filters_detail_delete_restore_export(app_and_obs) -> None:
    app, _ = app_and_obs
    _seed_archived_run(app, run_id="arch-1", started_at=10.0, algorithm_path="pkg.EvoGradient")
    _seed_archived_run(app, run_id="arch-2", started_at=20.0, algorithm_path="pkg.Trainer")

    with TestClient(app) as client:
        r = client.get("/archive?algorithm=EvoGradient&from=0&to=15&limit=10")
        assert r.status_code == 200
        rows = r.json()
        assert [row["run_id"] for row in rows] == ["arch-1"]

        detail = client.get("/archive/arch-1")
        assert detail.status_code == 200
        body = detail.json()
        assert body["summary"]["run_id"] == "arch-1"
        assert len(body["events"]) == 2

        summary_fallback = client.get("/runs/arch-1/summary")
        assert summary_fallback.status_code == 200
        events_fallback = client.get("/runs/arch-1/events?limit=10")
        assert events_fallback.status_code == 200
        assert len(events_fallback.json()["events"]) == 2

        restore = client.post("/archive/arch-1/restore")
        assert restore.status_code == 200
        assert restore.json()["ok"] is True
        live = client.get("/runs/arch-1/summary")
        assert live.status_code == 200
        assert live.json()["run_id"] == "arch-1"

        exported = client.post("/archive/_export?format=jsonl")
        assert exported.status_code == 200
        lines = [line for line in exported.text.strip().splitlines() if line.strip()]
        assert len(lines) >= 2
        parsed = [json.loads(line) for line in lines]
        assert all("summary" in item and "events" in item for item in parsed)

        deleted = client.delete("/archive/arch-2")
        assert deleted.status_code == 200
        assert deleted.json() == {"ok": True}
        missing = client.get("/archive/arch-2")
        assert missing.status_code == 404


def test_snapshot_only_on_terminal_events(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        start = {"type": "agent_event", "run_id": "r-term", "kind": "start", "metadata": {"is_root": True}}
        r1 = client.post("/_ingest", json=start)
        assert r1.status_code == 200
        assert app.state.archive_store.list_runs(limit=10) == []

        end = {"type": "agent_event", "run_id": "r-term", "kind": "end", "metadata": {"is_root": True}}
        r2 = client.post("/_ingest", json=end)
        assert r2.status_code == 200
        _wait_for_archive(app, "r-term")


def test_restart_survives_via_data_dir(tmp_path: Path) -> None:
    obs1 = WebDashboardObserver()
    app1 = create_app(observer=obs1, auto_register=False, data_dir=tmp_path)
    with TestClient(app1) as client:
        batch = [
            {
                "type": "algo_event",
                "run_id": "restart-1",
                "algorithm_path": "pkg.EvoGradient",
                "kind": "algo_start",
                "payload": {},
                "started_at": 100.0,
                "finished_at": None,
                "metadata": {},
            },
            {
                "type": "algo_event",
                "run_id": "restart-1",
                "algorithm_path": "pkg.EvoGradient",
                "kind": "algo_end",
                "payload": {"score": 1.0},
                "started_at": 101.0,
                "finished_at": 101.0,
                "metadata": {},
            },
        ]
        assert client.post("/_ingest", json=batch).status_code == 200
        _wait_for_archive(app1, "restart-1")

    obs2 = WebDashboardObserver()
    app2 = create_app(observer=obs2, auto_register=False, data_dir=tmp_path)
    with TestClient(app2) as client:
        live = client.get("/runs")
        assert live.status_code == 200
        assert live.json() == []

        archive = client.get("/archive")
        assert archive.status_code == 200
        run_ids = [row["run_id"] for row in archive.json()]
        assert "restart-1" in run_ids
