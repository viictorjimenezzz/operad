"""/_ingest accepts JSON arrays (batch mode)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def test_batch_broadcasts_all(app_and_obs) -> None:
    app, obs = app_and_obs
    q = obs.subscribe()
    batch = [
        {"type": "agent_event", "run_id": "r1", "kind": "start"},
        {"type": "algo_event", "run_id": "r1", "kind": "algo_start", "algorithm_path": "X",
         "payload": {}, "started_at": 1.0, "finished_at": None, "metadata": {}},
        {"type": "agent_event", "run_id": "r1", "kind": "end"},
    ]
    with TestClient(app) as client:
        r = client.post("/_ingest", json=batch)
        assert r.status_code == 200
    received = []
    while not q.empty():
        received.append(q.get_nowait())
    assert len(received) == 3


def test_batch_single_envelope_still_works(app_and_obs) -> None:
    app, obs = app_and_obs
    q = obs.subscribe()
    with TestClient(app) as client:
        r = client.post("/_ingest", json={"type": "agent_event", "run_id": "r2", "kind": "start"})
        assert r.status_code == 200
    assert not q.empty()


def test_batch_unknown_type_422(app_and_obs) -> None:
    app, _ = app_and_obs
    batch = [
        {"type": "agent_event", "run_id": "r3", "kind": "start"},
        {"type": "bad_type", "run_id": "r3"},
    ]
    with TestClient(app) as client:
        r = client.post("/_ingest", json=batch)
        assert r.status_code == 422


def test_batch_with_graph_envelope(app_and_obs) -> None:
    app, obs = app_and_obs
    q = obs.subscribe()
    batch = [
        {"type": "agent_event", "run_id": "r4", "kind": "start"},
        {"type": "graph_envelope", "run_id": "r4", "mermaid": "flowchart LR\n  A-->B"},
    ]
    with TestClient(app) as client:
        r = client.post("/_ingest", json=batch)
        assert r.status_code == 200
        # graph_envelope is not broadcast
        assert q.qsize() == 1
        assert q.get_nowait()["type"] == "agent_event"
        # but mermaid is stored
        r2 = client.get("/graph/r4")
        assert r2.status_code == 200
