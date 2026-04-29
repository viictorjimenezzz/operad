"""Synthetic run flagging: parent_run_id linkage and /runs filtering."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _seed(obs: WebDashboardObserver, parent_id: str, child_id: str) -> None:
    """Ingest one parent algo event and one synthetic child agent event."""
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": parent_id,
            "algorithm_path": "EvoGradient",
            "kind": "algo_start",
            "payload": {},
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "agent_event",
            "run_id": child_id,
            "agent_path": "Evaluator",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": 1.1,
            "finished_at": None,
            "metadata": {"parent_run_id": parent_id},
            "error": None,
        }
    )


def test_runs_hides_synthetic_by_default(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent1", "child1")
    with TestClient(app) as client:
        r = client.get("/runs")
        assert r.status_code == 200
        ids = [item["run_id"] for item in r.json()]
        assert "parent1" in ids
        assert "child1" not in ids


def test_runs_include_synthetic_shows_all(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent2", "child2")
    with TestClient(app) as client:
        r = client.get("/runs?include=synthetic")
        assert r.status_code == 200
        ids = {item["run_id"] for item in r.json()}
        assert {"parent2", "child2"} <= ids


def test_children_endpoint(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent3", "child3")
    with TestClient(app) as client:
        r = client.get("/runs/parent3/children")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["run_id"] == "child3"
        assert items[0]["synthetic"] is True
        assert items[0]["parent_run_id"] == "parent3"


def test_parent_endpoint(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent4", "child4")
    with TestClient(app) as client:
        r = client.get("/runs/child4/parent")
        assert r.status_code == 200
        assert r.json()["run_id"] == "parent4"


def test_parent_endpoint_non_synthetic_404(app_and_obs) -> None:
    app, obs = app_and_obs
    obs.registry.record_envelope(
        {"type": "algo_event", "run_id": "solo", "algorithm_path": "X",
         "kind": "algo_start", "payload": {}, "started_at": 1.0,
         "finished_at": None, "metadata": {}}
    )
    with TestClient(app) as client:
        assert client.get("/runs/solo/parent").status_code == 404


def test_tree_endpoint(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent5", "child5")
    with TestClient(app) as client:
        r = client.get("/runs/parent5/tree")
        assert r.status_code == 200
        body = r.json()
        assert body["root"]["run_id"] == "parent5"
        assert len(body["children"]) == 1
        assert body["children"][0]["run_id"] == "child5"


def test_summary_includes_synthetic_fields(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent6", "child6")
    child = obs.registry.get("child6")
    assert child is not None
    s = child.summary()
    assert s["synthetic"] is True
    assert s["parent_run_id"] == "parent6"


def test_algorithm_class_in_summary(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "parent7", "child7")
    parent = obs.registry.get("parent7")
    assert parent is not None
    assert parent.summary()["algorithm_class"] == "EvoGradient"


def test_optimisers_and_trainer_also_route_to_training_rail(app_and_obs) -> None:
    """Trainer and optimisers (OPRO/EvoGradient/...) belong on the
    Training rail while still remaining visible in the Algorithms rail.
    """
    app, obs = app_and_obs
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": "trainer-parent",
            "algorithm_path": "Trainer",
            "kind": "algo_start",
            "payload": {},
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": "opro-child",
            "algorithm_path": "OPROOptimizer",
            "kind": "algo_start",
            "payload": {},
            "started_at": 2.0,
            "finished_at": None,
            "metadata": {"parent_run_id": "trainer-parent"},
        }
    )

    with TestClient(app) as client:
        algos = client.get("/api/algorithms")
        trainings = client.get("/api/trainings")

    assert algos.status_code == 200
    assert trainings.status_code == 200
    algo_paths = {entry["algorithm_path"] for entry in algos.json()}
    assert {"Trainer", "OPROOptimizer"} <= algo_paths
    paths = {entry["algorithm_path"] for entry in trainings.json()}
    assert {"Trainer", "OPROOptimizer"} <= paths


def test_opro_endpoint_filters_opro_algorithm_runs(app_and_obs) -> None:
    app, obs = app_and_obs
    for run_id, path, ts in [
        ("opro-run", "OPRO", 1.0),
        ("beam-run", "Beam", 2.0),
    ]:
        obs.registry.record_envelope(
            {
                "type": "algo_event",
                "run_id": run_id,
                "algorithm_path": path,
                "kind": "algo_start",
                "payload": {},
                "started_at": ts,
                "finished_at": None,
                "metadata": {},
            }
        )

    with TestClient(app) as client:
        alias = client.get("/api/opro")
        filtered = client.get("/api/algorithms?path=OPRO")

    assert alias.status_code == 200
    assert filtered.status_code == 200
    assert [group["algorithm_path"] for group in alias.json()] == ["OPRO"]
    assert [group["algorithm_path"] for group in filtered.json()] == ["OPRO"]
    assert alias.json()[0]["runs"][0]["run_id"] == "opro-run"


def test_opro_endpoint_merges_contiguous_split_optimizer_steps(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_opro_step(obs, "opro-step-1", step=1, candidate="first", score=0.8, ts=1.0)
    _seed_opro_step(obs, "opro-step-2", step=2, candidate="second", score=0.9, ts=10.0)

    with TestClient(app) as client:
        alias = client.get("/api/opro")
        filtered = client.get("/api/algorithms?path=OPROOptimizer")
        trainings = client.get("/api/trainings")
        summary = client.get("/runs/opro-step-1/summary")
        events = client.get("/runs/opro-step-1/events?limit=20")
        iterations = client.get("/runs/opro-step-1/iterations.json")

    assert alias.status_code == 200
    assert filtered.status_code == 200
    assert trainings.status_code == 200
    assert summary.status_code == 200
    assert events.status_code == 200
    assert iterations.status_code == 200

    assert alias.json()[0]["count"] == 1
    assert filtered.json()[0]["count"] == 1
    assert trainings.json()[0]["count"] == 1
    merged = alias.json()[0]["runs"][0]
    assert merged["run_id"] == "opro-step-1"
    assert [row["metadata"]["step_index"] for row in merged["iterations"]] == [1, 1, 2, 2]
    assert summary.json()["event_counts"]["iteration"] == 4
    assert {event["run_id"] for event in events.json()["events"]} == {"opro-step-1"}
    assert [row["metadata"]["step_index"] for row in iterations.json()["iterations"]] == [
        1,
        1,
        2,
        2,
    ]


def _seed_opro_step(
    obs: WebDashboardObserver,
    run_id: str,
    *,
    step: int,
    candidate: str,
    score: float,
    ts: float,
) -> None:
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": "OPROOptimizer",
            "kind": "algo_start",
            "payload": {"params": ["task"], "history_window": 20, "max_retries": 3},
            "started_at": ts,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": "OPROOptimizer",
            "kind": "iteration",
            "payload": {
                "iter_index": step,
                "step_index": step,
                "phase": "propose",
                "param_path": "task",
                "candidate_value": candidate,
                "history_size": step,
            },
            "started_at": ts + 1.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": "OPROOptimizer",
            "kind": "iteration",
            "payload": {
                "iter_index": step,
                "step_index": step,
                "phase": "evaluate",
                "param_path": "task",
                "candidate_value": candidate,
                "score": score,
                "accepted": True,
            },
            "started_at": ts + 2.0,
            "finished_at": None,
            "metadata": {},
        }
    )
    obs.registry.record_envelope(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": "OPROOptimizer",
            "kind": "algo_end",
            "payload": {"steps": step, "best_score": score, "final_values": {"task": candidate}},
            "started_at": ts + 3.0,
            "finished_at": ts + 3.0,
            "metadata": {},
        }
    )
