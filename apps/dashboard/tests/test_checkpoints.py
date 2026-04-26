"""`/runs/{run_id}/checkpoints.{json,sse}` — per-epoch checkpoint timeline."""

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


def _epoch_end_event(
    run_id: str,
    epoch: int,
    train_loss: float,
    val_loss: float | None = None,
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Trainer",
        kind="iteration",
        payload={
            "phase": "epoch_end",
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "lr": 0.1 / (epoch + 1),
            "parameter_snapshot": {"role": f"role-{epoch}"},
            "hash_content": f"hash{epoch}",
        },
        started_at=1.0 + epoch,
        finished_at=1.5 + epoch,
    )


def test_checkpoints_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/checkpoints.json").status_code == 404


async def test_checkpoints_returns_epoch_end_events(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(_epoch_end_event("r1", 0, train_loss=0.9, val_loss=0.95))
    await obs.on_event(_epoch_end_event("r1", 1, train_loss=0.7, val_loss=0.75))
    await obs.on_event(_epoch_end_event("r1", 2, train_loss=0.5, val_loss=0.55))
    with TestClient(app) as client:
        entries = client.get("/runs/r1/checkpoints.json").json()
    assert [e["epoch"] for e in entries] == [0, 1, 2]
    assert entries[0]["train_loss"] == pytest.approx(0.9)
    assert entries[0]["val_loss"] == pytest.approx(0.95)
    assert entries[0]["score"] == pytest.approx(0.95)
    assert entries[0]["lr"] == pytest.approx(0.1)
    assert entries[0]["parameter_snapshot"]["role"] == "role-0"
    assert entries[0]["metric_snapshot"]["score"] == pytest.approx(0.95)


async def test_checkpoints_is_best_marks_lowest_score(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    await obs.on_event(_epoch_end_event("r2", 0, train_loss=0.9, val_loss=0.95))
    await obs.on_event(_epoch_end_event("r2", 1, train_loss=0.6, val_loss=0.62))
    await obs.on_event(_epoch_end_event("r2", 2, train_loss=0.7, val_loss=0.72))
    with TestClient(app) as client:
        entries = client.get("/runs/r2/checkpoints.json").json()
    best = [e for e in entries if e["is_best"]]
    assert len(best) == 1
    assert best[0]["epoch"] == 1


async def test_checkpoints_uses_train_loss_when_no_val(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r3")
    await obs.on_event(_epoch_end_event("r3", 0, train_loss=0.8, val_loss=None))
    await obs.on_event(_epoch_end_event("r3", 1, train_loss=0.5, val_loss=None))
    with TestClient(app) as client:
        entries = client.get("/runs/r3/checkpoints.json").json()
    assert entries[0]["val_loss"] is None
    assert entries[0]["score"] == pytest.approx(0.8)
    best = [e for e in entries if e["is_best"]]
    assert best[0]["epoch"] == 1


async def test_checkpoints_ignores_non_epoch_end_iterations(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r4")
    epoch_start = AlgorithmEvent(
        run_id="r4",
        algorithm_path="Trainer",
        kind="iteration",
        payload={"phase": "epoch_start", "epoch": 0},
        started_at=1.0,
        finished_at=None,
    )
    await obs.on_event(epoch_start)
    await obs.on_event(_epoch_end_event("r4", 0, train_loss=0.7))
    with TestClient(app) as client:
        entries = client.get("/runs/r4/checkpoints.json").json()
    assert len(entries) == 1
    assert entries[0]["epoch"] == 0
