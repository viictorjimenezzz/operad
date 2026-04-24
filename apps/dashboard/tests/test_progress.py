"""`/runs/{run_id}/progress.{json,sse}` — training progress snapshot."""

from __future__ import annotations

from collections import deque

import pytest
from fastapi.testclient import TestClient

from operad.runtime.events import AlgorithmEvent
from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver
from operad_dashboard.runs import RunInfo


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _seed(obs: WebDashboardObserver, run_id: str) -> None:
    obs.registry._runs[run_id] = RunInfo(  # type: ignore[attr-defined]
        run_id=run_id,
        started_at=0.0,
        last_event_at=0.0,
        state="running",
        events=deque(maxlen=1000),
    )


def _event(
    run_id: str,
    *,
    kind: str,
    algorithm_path: str = "Trainer",
    payload: dict | None = None,
    t: float = 0.0,
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path=algorithm_path,
        kind=kind,  # type: ignore[arg-type]
        payload=payload or {},
        started_at=t,
        finished_at=t,
    )


def test_progress_json_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/progress.json").status_code == 404


async def test_progress_json_after_batches(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(
        _event("r1", kind="algo_start", payload={"epochs": 2}, t=1.0)
    )
    await obs.on_event(
        _event("r1", kind="iteration", payload={"phase": "epoch_start", "epoch": 0}, t=1.0)
    )
    await obs.on_event(
        _event(
            "r1",
            kind="batch_start",
            algorithm_path="DataLoader",
            payload={"batch_index": 0, "batch_size": 1},
            t=1.1,
        )
    )
    await obs.on_event(
        _event(
            "r1",
            kind="batch_end",
            algorithm_path="DataLoader",
            payload={"batch_index": 0, "duration_ms": 100.0},
            t=1.2,
        )
    )

    with TestClient(app) as client:
        snap = client.get("/runs/r1/progress.json").json()
    assert snap["epochs_total"] == 2
    assert snap["epoch"] == 0
    assert snap["batch"] == 1
    assert snap["rate_batches_per_s"] > 0
    assert snap["finished"] is False


async def test_progress_json_finished_after_algo_end(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    await obs.on_event(
        _event("r2", kind="algo_start", payload={"epochs": 1})
    )
    await obs.on_event(_event("r2", kind="algo_end"))
    with TestClient(app) as client:
        snap = client.get("/runs/r2/progress.json").json()
    assert snap["finished"] is True


async def test_progress_json_empty_snapshot_before_algo_start(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r3")
    with TestClient(app) as client:
        snap = client.get("/runs/r3/progress.json").json()
    assert snap["epochs_total"] is None
    assert snap["finished"] is False
