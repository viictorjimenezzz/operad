from __future__ import annotations

from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


def _seed_agent_run(
    obs: WebDashboardObserver,
    *,
    run_id: str,
    root_path: str,
    hash_content: str,
    started_at: float,
    terminal_kind: str = "end",
) -> None:
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": root_path,
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": started_at,
            "finished_at": None,
            "metadata": {"is_root": True, "hash_content": hash_content},
            "error": None,
        }
    )
    if terminal_kind not in {"end", "error"}:
        return
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": root_path,
            "kind": terminal_kind,
            "input": None,
            "output": {"prompt_tokens": 1, "completion_tokens": 1} if terminal_kind == "end" else None,
            "started_at": started_at + 0.1,
            "finished_at": started_at + 0.2,
            "metadata": {"is_root": True, "hash_content": hash_content},
            "error": {"type": "RuntimeError", "message": "boom"} if terminal_kind == "error" else None,
        }
    )


def test_agent_classes_groups_instances_by_class_name() -> None:
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    _seed_agent_run(
        obs,
        run_id="run-a1",
        root_path="pipeline.class_a",
        hash_content="hash-a1",
        started_at=10.0,
    )
    _seed_agent_run(
        obs,
        run_id="run-a2",
        root_path="pipeline.class_a",
        hash_content="hash-a2",
        started_at=20.0,
        terminal_kind="start",
    )
    _seed_agent_run(
        obs,
        run_id="run-b1",
        root_path="pipeline.class_b",
        hash_content="hash-b1",
        started_at=30.0,
        terminal_kind="error",
    )
    # Algorithm orchestrator rows should not appear on the agents rail.
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": "algo-1",
            "algorithm_path": "Sweep",
            "kind": "algo_start",
            "payload": {},
            "started_at": 40.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    # Synthetic children should also be excluded.
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": "child-1",
            "agent_path": "pipeline.class_a",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": 50.0,
            "finished_at": None,
            "metadata": {"parent_run_id": "algo-1"},
            "error": None,
        }
    )

    with TestClient(app) as client:
        response = client.get("/api/agent-classes")

    assert response.status_code == 200
    rows = response.json()
    assert [row["class_name"] for row in rows] == ["class_b", "class_a"]
    class_a = next(row for row in rows if row["class_name"] == "class_a")
    class_b = next(row for row in rows if row["class_name"] == "class_b")

    assert class_a["instance_count"] == 2
    assert class_a["running"] == 1
    assert class_a["errors"] == 0
    assert [item["hash_content"] for item in class_a["instances"]] == ["hash-a2", "hash-a1"]

    assert class_b["instance_count"] == 1
    assert class_b["running"] == 0
    assert class_b["errors"] == 1
    assert class_b["instances"][0]["hash_content"] == "hash-b1"
