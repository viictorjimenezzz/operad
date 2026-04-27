from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


def test_agent_group_parameters_returns_latest_trainable_snapshot() -> None:
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": "r1",
            "agent_path": "Root",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {"is_root": True, "hash_content": "abc123"},
            "error": None,
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": "r1",
            "algorithm_path": "Trainer",
            "kind": "iteration",
            "payload": {
                "phase": "epoch_end",
                "epoch": 0,
                "parameter_snapshot": {"role": "role-v1"},
            },
            "started_at": 2.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": "r1",
            "algorithm_path": "Trainer",
            "kind": "iteration",
            "payload": {
                "phase": "epoch_end",
                "epoch": 1,
                "parameter_snapshot": {"role": "role-v2", "task": "task-v2"},
            },
            "started_at": 3.0,
            "finished_at": None,
            "metadata": {},
        }
    )

    with TestClient(app) as client:
        response = client.get("/api/agents/abc123/parameters")

    assert response.status_code == 200
    body = response.json()
    assert body["paths"] == ["role", "task"]
    assert body["series"][0]["run_id"] == "r1"
    assert body["series"][0]["values"]["role"] == {
        "value": "role-v2",
        "hash": hashlib.sha256(repr("role-v2").encode("utf-8")).hexdigest()[:16],
    }
