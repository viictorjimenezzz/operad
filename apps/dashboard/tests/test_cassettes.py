"""`/cassettes` API tests: discovery, replay, determinism, and path safety."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _trace_rows() -> list[dict]:
    return [
        {
            "event": "agent",
            "run_id": "trace-run",
            "agent_path": "Pipeline",
            "kind": "start",
            "input": {"text": "hi"},
            "output": None,
            "started_at": 1000.0,
            "finished_at": None,
            "metadata": {"is_root": True},
        },
        {
            "event": "agent",
            "run_id": "trace-run",
            "agent_path": "Pipeline",
            "kind": "end",
            "input": {"text": "hi"},
            "output": {"answer": "ok"},
            "started_at": 1000.0,
            "finished_at": 1000.1,
            "metadata": {"is_root": True},
        },
    ]


def test_cassettes_discovery_uses_env_root(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = app_and_obs
    root = tmp_path / "my-cassettes"
    _write_jsonl(root / "trace.jsonl", _trace_rows())
    monkeypatch.setenv("OPERAD_DASHBOARD_CASSETTE_DIR", str(root))

    with TestClient(app) as client:
        r = client.get("/cassettes")
        assert r.status_code == 200
        body = r.json()

    assert len(body) == 1
    assert body[0]["path"] == "trace.jsonl"
    assert body[0]["type"] == "trace"
    assert body[0]["metadata"]["run_id"] == "trace-run"


def test_cassettes_discovery_uses_default_root(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = app_and_obs
    monkeypatch.delenv("OPERAD_DASHBOARD_CASSETTE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    _write_jsonl(tmp_path / ".cassettes" / "default.jsonl", _trace_rows())

    with TestClient(app) as client:
        r = client.get("/cassettes")
        assert r.status_code == 200
        body = r.json()

    assert [x["path"] for x in body] == ["default.jsonl"]


def test_cassette_replay_creates_run_and_emits(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, obs = app_and_obs
    root = tmp_path / "cass"
    _write_jsonl(root / "replay.jsonl", _trace_rows())
    monkeypatch.setenv("OPERAD_DASHBOARD_CASSETTE_DIR", str(root))

    q = obs.subscribe()
    with TestClient(app) as client:
        r = client.post("/cassettes/replay?delay_ms=0", json={"path": "replay.jsonl"})
        assert r.status_code == 200
        run_id = r.json()["run_id"]

    assert q.qsize() == 2
    run = obs.registry.get(run_id)
    assert run is not None
    assert run.event_total == 2


def test_determinism_check_passes_for_valid_cassette(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = app_and_obs
    root = tmp_path / "cass"
    _write_jsonl(root / "ok.jsonl", _trace_rows())
    monkeypatch.setenv("OPERAD_DASHBOARD_CASSETTE_DIR", str(root))

    with TestClient(app) as client:
        r = client.post("/cassettes/determinism-check", json={"path": "ok.jsonl"})
        assert r.status_code == 200
        body = r.json()

    assert body["ok"] is True
    assert body["diff"] == []


def test_determinism_check_fails_for_tampered_cassette(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = app_and_obs
    root = tmp_path / "cass"
    tampered = root / "tampered.jsonl"
    tampered.parent.mkdir(parents=True, exist_ok=True)
    tampered.write_text(
        json.dumps(_trace_rows()[0]) + "\n" + "{bad-json}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPERAD_DASHBOARD_CASSETTE_DIR", str(root))

    with TestClient(app) as client:
        r = client.post("/cassettes/determinism-check", json={"path": "tampered.jsonl"})
        assert r.status_code == 200
        body = r.json()

    assert body["ok"] is False
    assert body["diff"]
    assert body["diff"][0]["field"] == "line"


def test_cassette_path_traversal_rejected(app_and_obs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = app_and_obs
    root = tmp_path / "cass"
    _write_jsonl(root / "safe.jsonl", _trace_rows())
    outside = tmp_path / "outside.jsonl"
    _write_jsonl(outside, _trace_rows())
    monkeypatch.setenv("OPERAD_DASHBOARD_CASSETTE_DIR", str(root))

    with TestClient(app) as client:
        r = client.post("/cassettes/replay?delay_ms=0", json={"path": "../outside.jsonl"})
    assert r.status_code == 400
