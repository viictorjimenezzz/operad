"""GET /runs/{run_id} — run detail page rendered from run_detail.html."""

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


def test_run_detail_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/runs/nope-run-id")
        assert r.status_code == 404


def test_run_detail_renders_partials(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "abc123")
    with TestClient(app) as client:
        r = client.get("/runs/abc123")
        assert r.status_code == 200
        html = r.text
        assert 'id="panel-progress"' in html
        assert 'id="panel-fitness"' in html
        assert 'id="panel-mutations"' in html
        assert 'id="panel-drift"' in html
        assert 'window.OPERAD_RUN_ID = "abc123"' in html
