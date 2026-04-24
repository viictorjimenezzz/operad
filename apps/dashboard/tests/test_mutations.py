"""`/runs/{run_id}/mutations.{json,sse}` — per-op success matrices."""

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


def _gen(
    run_id: str,
    gen_index: int,
    attempts: dict[str, int],
    successes: dict[str, int],
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="EvoGradient",
        kind="generation",
        payload={
            "gen_index": gen_index,
            "population_scores": [0.1] * sum(attempts.values()),
            "op_attempt_counts": attempts,
            "op_success_counts": successes,
        },
        started_at=1.0 + gen_index,
        finished_at=1.5 + gen_index,
    )


def test_mutations_json_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/mutations.json").status_code == 404


async def test_mutations_json_aggregates_matrices(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(_gen("r1", 0, {"mutate_role": 3, "swap": 1}, {"mutate_role": 2, "swap": 0}))
    await obs.on_event(_gen("r1", 1, {"mutate_role": 2, "swap": 2}, {"mutate_role": 1, "swap": 1}))
    with TestClient(app) as client:
        payload = client.get("/runs/r1/mutations.json").json()
    assert payload["gens"] == [0, 1]
    # Ops sorted by total attempts desc: mutate_role (5) > swap (3).
    assert payload["ops"] == ["mutate_role", "swap"]
    assert payload["success"] == [[2, 1], [0, 1]]
    assert payload["attempts"] == [[3, 2], [1, 2]]


async def test_mutations_json_empty_for_runs_without_counts(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    missing = AlgorithmEvent(
        run_id="r2",
        algorithm_path="EvoGradient",
        kind="generation",
        payload={"gen_index": 0, "population_scores": [0.1, 0.2]},
        started_at=1.0, finished_at=1.5,
    )
    await obs.on_event(missing)
    with TestClient(app) as client:
        payload = client.get("/runs/r2/mutations.json").json()
    assert payload == {"gens": [], "ops": [], "success": [], "attempts": []}
