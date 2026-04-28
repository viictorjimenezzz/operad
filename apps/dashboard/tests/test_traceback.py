"""`/runs/{run_id}/traceback.ndjson` route tests."""

from __future__ import annotations

import json
from pathlib import Path

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


def _seed_run_with_traceback(
    obs: WebDashboardObserver,
    *,
    run_id: str,
    traceback_path: str | None,
) -> None:
    obs.registry._runs[run_id] = RunInfo(  # type: ignore[attr-defined]
        run_id=run_id,
        started_at=1.0,
        last_event_at=2.0,
        state="ended",
        traceback_path=traceback_path,
    )


def test_traceback_ndjson_returns_frames(app_and_obs, tmp_path: Path) -> None:
    app, obs = app_and_obs
    tb_path = tmp_path / "traceback.ndjson"
    tb_path.write_text(
        "\n".join(
            [
                json.dumps({"agent_path": "root.stage_1", "gradient": {"message": "first"}}),
                json.dumps({"agent_path": "root.stage_0", "gradient": {"message": "second"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _seed_run_with_traceback(obs, run_id="run-1", traceback_path=str(tb_path))

    with TestClient(app) as client:
        response = client.get("/runs/run-1/traceback.ndjson")
    assert response.status_code == 200
    assert response.json() == {
        "frames": [
            {"agent_path": "root.stage_1", "gradient": {"message": "first"}},
            {"agent_path": "root.stage_0", "gradient": {"message": "second"}},
        ]
    }


def test_traceback_ndjson_404_when_missing_path(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run_with_traceback(obs, run_id="run-2", traceback_path=None)

    with TestClient(app) as client:
        response = client.get("/runs/run-2/traceback.ndjson")
    assert response.status_code == 404
    assert response.json()["detail"] == "no traceback for this run"


def test_traceback_ndjson_404_when_file_not_found(app_and_obs, tmp_path: Path) -> None:
    app, obs = app_and_obs
    missing = tmp_path / "missing.ndjson"
    _seed_run_with_traceback(obs, run_id="run-3", traceback_path=str(missing))

    with TestClient(app) as client:
        response = client.get("/runs/run-3/traceback.ndjson")
    assert response.status_code == 404
    assert response.json()["detail"] == "traceback file missing on disk"
