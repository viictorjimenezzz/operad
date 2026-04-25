"""GET /runs/{run_id} — SPA shell served for all client-side routes."""

from __future__ import annotations

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


def _seed(obs: WebDashboardObserver, run_id: str) -> None:
    from collections import deque

    obs.registry._runs[run_id] = RunInfo(  # type: ignore[attr-defined]
        run_id=run_id,
        started_at=1.0,
        last_event_at=2.0,
        state="running",
        events=deque(maxlen=1000),
    )


def test_run_detail_spa_shell_for_known_run(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "abc123")
    with TestClient(app) as client:
        r = client.get("/runs/abc123")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_run_detail_spa_shell_for_unknown_run(app_and_obs) -> None:
    # SPA handles 404 client-side; server always returns the shell.
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/runs/nope-run-id")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_run_summary_api_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope-run-id/summary").status_code == 404


def test_run_summary_api_returns_data(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "abc123")
    with TestClient(app) as client:
        r = client.get("/runs/abc123/summary")
        assert r.status_code == 200
        assert r.json()["run_id"] == "abc123"


def test_create_app_strips_trailing_slash_from_langfuse_url() -> None:
    obs = WebDashboardObserver()
    app = create_app(
        observer=obs,
        auto_register=False,
        langfuse_url="http://localhost:3000/",
    )
    _seed(obs, "abc")
    with TestClient(app) as client:
        # langfuse_url is exposed via /api/manifest, not injected into HTML
        r = client.get("/api/manifest")
        assert r.json()["langfuseUrl"] == "http://localhost:3000"
