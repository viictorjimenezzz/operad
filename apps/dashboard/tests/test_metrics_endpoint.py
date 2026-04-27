from __future__ import annotations

from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


def _seed_agent_run(
    obs: WebDashboardObserver,
    *,
    run_id: str,
    started_at: float,
    hash_content: str,
    quality: float,
) -> None:
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Root",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": started_at,
            "finished_at": None,
            "metadata": {"is_root": True, "hash_content": hash_content},
            "error": None,
        }
    )
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Root",
            "kind": "end",
            "input": None,
            "output": {"prompt_tokens": 10, "completion_tokens": 5},
            "started_at": started_at + 0.2,
            "finished_at": started_at + 0.2,
            "metadata": {
                "is_root": True,
                "hash_content": hash_content,
                "metrics": {"quality": quality},
            },
            "error": None,
        }
    )


def test_agent_group_metrics_returns_four_run_series() -> None:
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    for i in range(4):
        _seed_agent_run(
            obs,
            run_id=f"r{i}",
            started_at=100.0 + i,
            hash_content="abc123",
            quality=float(i) / 10.0,
        )

    with TestClient(app) as client:
        response = client.get("/api/agents/abc123/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["hash_content"] == "abc123"
    assert body["metrics"]["latency_ms"]["unit"] == "ms"
    assert len(body["metrics"]["latency_ms"]["series"]) == 4
    assert body["metrics"]["prompt_tokens"]["series"][0]["value"] == 10
    assert body["metrics"]["completion_tokens"]["series"][0]["value"] == 5
    assert [p["value"] for p in body["metrics"]["quality"]["series"]] == [
        0.0,
        0.1,
        0.2,
        0.3,
    ]


def test_agent_group_metrics_empty_group_returns_empty_shape() -> None:
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)

    with TestClient(app) as client:
        response = client.get("/api/agents/missing/metrics")

    assert response.status_code == 200
    assert response.json() == {"hash_content": "missing", "metrics": {}}
