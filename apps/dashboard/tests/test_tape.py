"""`/runs/{run_id}/tape.json` — tape-entry snapshots for Trainer debugging."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from operad.runtime.observers.base import AgentEvent
from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _agent_end(run_id: str, tape_entry: dict[str, object] | None = None) -> AgentEvent:
    metadata: dict[str, object] = {"is_root": True}
    if tape_entry is not None:
        metadata["tape_entry"] = tape_entry
    return AgentEvent(
        run_id=run_id,
        agent_path="Root.leaf",
        kind="end",  # type: ignore[arg-type]
        input=None,
        output=None,
        error=None,
        started_at=1.0,
        finished_at=1.1,
        metadata=metadata,
    )


def test_tape_json_404_when_run_is_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        response = client.get("/runs/nope/tape.json")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "reason": "unknown run_id"}


async def test_tape_json_returns_captured_entries(app_and_obs) -> None:
    app, obs = app_and_obs
    await obs.on_event(
        _agent_end(
            "run-with-tape",
            {
                "agent_path": "Root.leaf",
                "input_hash": "hash-in",
                "output_hash": "hash-out",
                "param_path": "Planner.role",
                "step_index": 2,
            },
        )
    )

    with TestClient(app) as client:
        response = client.get("/runs/run-with-tape/tape.json")

    assert response.status_code == 200
    assert response.json() == {
        "entries": [
            {
                "agent_path": "Root.leaf",
                "input_hash": "hash-in",
                "output_hash": "hash-out",
                "param_path": "Planner.role",
                "step_index": 2,
            }
        ]
    }
