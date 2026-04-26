"""`/runs/{run_id}/gradients.{json,sse}` — TextualGradient critique log."""

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
    obs.registry._runs[run_id] = RunInfo(
        run_id=run_id,
        started_at=1.0,
        last_event_at=2.0,
        state="running",
        events=deque(maxlen=1000),
    )


def _gradient_event(run_id: str, epoch: int, batch: int, message: str) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Trainer",
        kind="gradient_applied",
        payload={
            "epoch": epoch,
            "batch": batch,
            "message": message,
            "severity": "medium",
            "target_paths": ["role", "task"],
            "by_field": {"role": "role critique", "task": "task critique"},
            "applied_diff": f"- old role\n+ new role (epoch {epoch})",
        },
        started_at=1.0 + epoch,
        finished_at=1.5 + epoch,
    )


def test_gradients_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/gradients.json").status_code == 404


async def test_gradients_returns_empty_when_no_events(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    with TestClient(app) as client:
        entries = client.get("/runs/r1/gradients.json").json()
    assert entries == []


async def test_gradients_returns_gradient_entries(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    await obs.on_event(_gradient_event("r2", 0, 5, "role too vague"))
    await obs.on_event(_gradient_event("r2", 1, 3, "task ambiguous"))
    with TestClient(app) as client:
        entries = client.get("/runs/r2/gradients.json").json()
    assert len(entries) == 2
    assert entries[0]["epoch"] == 0
    assert entries[0]["batch"] == 5
    assert entries[0]["message"] == "role too vague"
    assert entries[0]["severity"] == "medium"
    assert "role" in entries[0]["target_paths"]
    assert entries[1]["epoch"] == 1


async def test_gradients_ignores_non_gradient_events(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r3")
    other = AlgorithmEvent(
        run_id="r3",
        algorithm_path="Trainer",
        kind="iteration",
        payload={"phase": "epoch_end", "epoch": 0, "train_loss": 0.5},
        started_at=1.0,
        finished_at=None,
    )
    await obs.on_event(other)
    with TestClient(app) as client:
        entries = client.get("/runs/r3/gradients.json").json()
    assert entries == []
