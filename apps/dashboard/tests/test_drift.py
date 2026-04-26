"""`/runs/{run_id}/drift.{json,sse}` — PromptDrift timeline endpoint."""

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
        started_at=1.0,
        last_event_at=2.0,
        state="running",
        events=deque(maxlen=1000),
    )


def _drift_event(run_id: str, epoch: int, changed: list[str]) -> AlgorithmEvent:
    changes = [
        {
            "path": name,
            "before_text": f"before {name} e{epoch}",
            "after_text": f"after {name} e{epoch}",
        }
        for name in changed
    ]
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="PromptDrift",
        kind="iteration",
        payload={
            "epoch": epoch,
            "before_text": changes[0]["before_text"] if changes else "",
            "after_text": changes[0]["after_text"] if changes else "",
            "selected_path": changes[0]["path"] if changes else "",
            "changes": changes,
            "changed_params": changed,
            "delta_count": len(changed),
        },
        started_at=1.0 + epoch,
        finished_at=1.5 + epoch,
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
        },
        started_at=2.0 + epoch,
        finished_at=2.5 + epoch,
    )


def test_drift_json_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/drift.json").status_code == 404


async def test_drift_json_returns_timeline(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(_drift_event("r1", 0, ["role"]))
    await obs.on_event(_drift_event("r1", 1, ["role", "rules[0]"]))
    with TestClient(app) as client:
        entries = client.get("/runs/r1/drift.json").json()
    assert [e["epoch"] for e in entries] == [0, 1]
    assert entries[1]["changed_params"] == ["role", "rules[0]"]
    assert entries[1]["delta_count"] == 2
    assert entries[0]["before_text"].startswith("before role")
    assert entries[1]["changes"][1]["path"] == "rules[0]"


async def test_drift_json_ignores_non_drift_iterations(app_and_obs) -> None:
    """A PromptDrift iteration should be picked up, but Trainer iterations shouldn't."""
    app, obs = app_and_obs
    _seed(obs, "r2")
    trainer_iter = AlgorithmEvent(
        run_id="r2",
        algorithm_path="Trainer",
        kind="iteration",
        payload={"phase": "epoch_start", "epoch": 0},
        started_at=1.0, finished_at=None,
    )
    await obs.on_event(trainer_iter)
    await obs.on_event(_drift_event("r2", 0, ["task"]))
    with TestClient(app) as client:
        entries = client.get("/runs/r2/drift.json").json()
    assert [e["epoch"] for e in entries] == [0]
    assert entries[0]["changed_params"] == ["task"]


async def test_drift_json_attaches_nearest_gradient_critique(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r3")
    await obs.on_event(_gradient_event("r3", 0, 1, "first critique"))
    await obs.on_event(_gradient_event("r3", 0, 3, "latest critique"))
    await obs.on_event(_drift_event("r3", 0, ["role"]))
    with TestClient(app) as client:
        entries = client.get("/runs/r3/drift.json").json()
    assert entries[0]["critique"] == "latest critique"
    assert entries[0]["gradient_batch"] == 3
