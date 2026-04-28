"""High-level dashboard smoke tests for every algorithm rail."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from operad.runtime.events import AlgorithmEvent
from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _event(
    run_id: str,
    algorithm_path: str,
    kind: str,
    payload: dict,
    timestamp: float,
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path=algorithm_path,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,
        started_at=timestamp,
        finished_at=timestamp + 0.1,
    )


async def _seed_run(obs: WebDashboardObserver, run_id: str, algorithm_path: str) -> None:
    await obs.on_event(
        _event(
            run_id,
            algorithm_path,
            "algo_start",
            {"root_path": f"{algorithm_path}.agent", "max_iter": 3, "threshold": 0.8},
            1.0,
        )
    )
    for event in _class_events(run_id, algorithm_path):
        await obs.on_event(event)
    await obs.on_event(_event(run_id, algorithm_path, "algo_end", {"score": 0.9}, 9.0))


def _class_events(run_id: str, algorithm_path: str) -> list[AlgorithmEvent]:
    if algorithm_path == "Sweep":
        return [
            _event(
                run_id,
                algorithm_path,
                "cell",
                {"cell_index": 0, "parameters": {"temperature": 0.2}, "score": 0.72},
                2.0,
            )
        ]
    if algorithm_path == "Beam":
        return [
            _event(
                run_id,
                algorithm_path,
                "candidate",
                {"candidate_index": 0, "iter_index": 0, "score": 0.81, "text": "candidate"},
                2.0,
            ),
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "prune", "score": 0.81, "top_indices": [0]},
                3.0,
            ),
        ]
    if algorithm_path == "Debate":
        return [
            _event(
                run_id,
                algorithm_path,
                "round",
                {
                    "round_index": 0,
                    "proposals": [{"author": "a", "content": "proposal"}],
                    "critiques": [{"target_author": "a", "comments": "solid", "score": 0.7}],
                    "scores": [0.7],
                },
                2.0,
            )
        ]
    if algorithm_path == "EvoGradient":
        return [
            _event(
                run_id,
                algorithm_path,
                "generation",
                {
                    "gen_index": 0,
                    "population_scores": [0.2, 0.8],
                    "survivor_indices": [1],
                    "op_attempt_counts": {"role": 2},
                    "op_success_counts": {"role": 1},
                },
                2.0,
            )
        ]
    if algorithm_path == "Trainer":
        return [
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {
                    "iter_index": 0,
                    "phase": "epoch_end",
                    "epoch": 0,
                    "train_loss": 0.42,
                    "val_loss": 0.5,
                    "lr": 0.001,
                    "parameter_snapshot": {"role": "critic"},
                },
                2.0,
            ),
            _event(
                run_id,
                algorithm_path,
                "batch_end",
                {"step": 1, "batch_index": 0, "batch_size": 4, "train_loss": 0.42, "lr": 0.001},
                3.0,
            ),
            _event(
                run_id,
                algorithm_path,
                "gradient_applied",
                {"epoch": 0, "batch": 0, "message": "tighten role", "target_paths": ["role"]},
                4.0,
            ),
        ]
    if algorithm_path == "OPRO":
        return [
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "evaluate", "score": 0.64, "text": "prompt"},
                2.0,
            )
        ]
    if algorithm_path == "SelfRefine":
        return [
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "reflect", "score": 0.55, "text": "draft"},
                2.0,
            )
        ]
    if algorithm_path == "AutoResearcher":
        return [
            _event(run_id, algorithm_path, "plan", {"attempt_index": 0, "plan": {"q": "x"}}, 2.0),
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "attempt", "score": 0.66, "text": "answer"},
                3.0,
            ),
        ]
    if algorithm_path == "TalkerReasoner":
        return [
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "turn", "score": 0.5, "text": "turn"},
                2.0,
            )
        ]
    if algorithm_path == "VerifierAgent":
        return [
            _event(
                run_id,
                algorithm_path,
                "iteration",
                {"iter_index": 0, "phase": "verify", "score": 0.91, "text": "accepted"},
                2.0,
            )
        ]
    raise AssertionError(f"unhandled algorithm smoke class: {algorithm_path}")


@pytest.mark.parametrize(
    ("algorithm_path", "endpoints"),
    [
        ("Sweep", ["/sweep.json"]),
        ("Beam", ["/iterations.json"]),
        ("Debate", ["/debate.json"]),
        ("EvoGradient", ["/fitness.json", "/mutations.json"]),
        ("Trainer", ["/fitness.json", "/drift.json", "/checkpoints.json", "/tape.json"]),
        ("OPRO", ["/iterations.json"]),
        ("SelfRefine", ["/iterations.json"]),
        ("AutoResearcher", ["/iterations.json"]),
        ("TalkerReasoner", []),
        ("VerifierAgent", ["/iterations.json"]),
    ],
)
async def test_algorithm_rail_smoke(app_and_obs, algorithm_path: str, endpoints: list[str]) -> None:
    app, obs = app_and_obs
    run_id = f"smoke-{algorithm_path.lower()}"
    await _seed_run(obs, run_id, algorithm_path)

    with TestClient(app) as client:
        summary = client.get(f"/runs/{run_id}/summary")
        assert summary.status_code == 200
        body = summary.json()
        assert body["is_algorithm"] is True
        assert body["algorithm_path"] == algorithm_path
        assert body["algorithm_class"] == algorithm_path
        assert body["event_total"] >= 2

        events = client.get(f"/runs/{run_id}/events?limit=20")
        assert events.status_code == 200
        assert events.json()["events"]

        children = client.get(f"/runs/{run_id}/children")
        assert children.status_code == 200
        assert children.json() == []

        for suffix in endpoints:
            response = client.get(f"/runs/{run_id}{suffix}")
            assert response.status_code == 200
