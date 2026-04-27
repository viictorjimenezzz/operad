from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


def _seed_run(obs: WebDashboardObserver) -> None:
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": "r-notes",
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
            "type": "agent_event",
            "run_id": "r-notes",
            "agent_path": "Root",
            "kind": "end",
            "input": None,
            "output": {},
            "started_at": 2.0,
            "finished_at": 2.0,
            "metadata": {"is_root": True, "hash_content": "abc123"},
            "error": None,
        }
    )


def test_patch_run_notes_updates_summary_and_archive(tmp_path: Path) -> None:
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False, data_dir=tmp_path)
    _seed_run(obs)

    with TestClient(app) as client:
        response = client.patch(
            "/api/runs/r-notes/notes",
            json={"markdown": "# note\n\nbody"},
        )
        summary = client.get("/runs/r-notes/summary")

    assert response.status_code == 200
    assert response.json()["notes_markdown"] == "# note\n\nbody"
    assert summary.status_code == 200
    assert summary.json()["notes_markdown"] == "# note\n\nbody"

    archived = app.state.archive_store.get_run("r-notes")
    assert archived is not None
    assert archived["summary"]["notes_markdown"] == "# note\n\nbody"
