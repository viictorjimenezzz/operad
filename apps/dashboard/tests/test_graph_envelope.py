"""/_ingest accepts graph_envelope and populates /graph/{run_id}."""

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


def test_graph_envelope_populates_cache(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.post(
            "/_ingest",
            json={"type": "graph_envelope", "run_id": "r1", "mermaid": "flowchart LR\n  A-->B"},
        )
        assert r.status_code == 200
        r2 = client.get("/graph/r1")
        assert r2.status_code == 200
        assert r2.json() == {"mermaid": "flowchart LR\n  A-->B"}


def test_graph_envelope_not_broadcast(app_and_obs) -> None:
    app, obs = app_and_obs
    q = obs.subscribe()
    with TestClient(app) as client:
        client.post(
            "/_ingest",
            json={"type": "graph_envelope", "run_id": "r2", "mermaid": "flowchart LR\n  X-->Y"},
        )
    assert q.empty()


def test_unknown_envelope_type_422(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.post("/_ingest", json={"type": "mystery_type", "run_id": "r3"})
        assert r.status_code == 422
        assert "mystery_type" in r.json()["detail"]


def test_graph_envelope_overwrites_mermaid(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        client.post("/_ingest", json={"type": "graph_envelope", "run_id": "r4", "mermaid": "v1"})
        client.post("/_ingest", json={"type": "graph_envelope", "run_id": "r4", "mermaid": "v2"})
        r = client.get("/graph/r4")
        assert r.json()["mermaid"] == "v2"
