"""FastAPI app: /runs, /graph/{id}, /stream, /_ingest."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver
from operad_dashboard.runs import RunInfo


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def test_index_renders(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_api_manifest(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "dashboard"
        assert "version" in body


def test_spa_catch_all_serves_run_detail(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        # Any /runs/{run_id} (no further suffix) is an SPA route now.
        r = client.get("/runs/abc")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_runs_empty(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/runs")
        assert r.status_code == 200
        assert r.json() == []


def test_runs_after_seed(app_and_obs) -> None:
    app, obs = app_and_obs
    obs.registry._runs["abc"] = RunInfo(  # type: ignore[attr-defined]
        run_id="abc", started_at=1.0, last_event_at=2.0, state="running"
    )
    with TestClient(app) as client:
        r = client.get("/runs")
        items = r.json()
        assert len(items) == 1
        assert items[0]["run_id"] == "abc"
        assert items[0]["state"] == "running"
        assert items[0]["has_graph"] is False


def test_graph_unknown_run_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/graph/nope").status_code == 404


def test_graph_known_run(app_and_obs) -> None:
    app, obs = app_and_obs
    obs.registry._runs["xyz"] = RunInfo(  # type: ignore[attr-defined]
        run_id="xyz",
        started_at=1.0,
        last_event_at=2.0,
        state="ended",
        mermaid="flowchart LR\n    A --> B",
    )
    with TestClient(app) as client:
        r = client.get("/graph/xyz")
        assert r.status_code == 200
        assert r.json() == {"mermaid": "flowchart LR\n    A --> B"}


def test_ingest_broadcasts_to_subscribers(app_and_obs) -> None:
    app, obs = app_and_obs
    q = obs.subscribe()
    with TestClient(app) as client:
        env = {"type": "agent_event", "run_id": "r1", "kind": "start"}
        r = client.post("/_ingest", json=env)
        assert r.status_code == 200
        assert q.get_nowait() == env


async def test_stream_yields_first_event(app_and_obs) -> None:
    import httpx

    app, obs = app_and_obs
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream("GET", "/stream", timeout=5.0) as resp:
            assert resp.status_code == 200
            seen: list[dict] = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    seen.append(json.loads(line[5:].strip()))
                    break
            assert seen
            assert seen[0]["type"] in {"slot_occupancy", "cost_update"}
