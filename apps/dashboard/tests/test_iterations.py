"""`/runs/{run_id}/iterations.{json,sse}` — generic iteration events endpoint."""

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


def _verifier_start(run_id: str, max_iter: int, threshold: float) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="VerifierLoop",
        kind="algo_start",
        payload={"max_iter": max_iter, "threshold": threshold},
        started_at=1.0,
        finished_at=None,
    )


def _verifier_iter(run_id: str, iter_index: int, score: float) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="VerifierLoop",
        kind="iteration",
        payload={"iter_index": iter_index, "phase": "verify", "score": score},
        started_at=1.0 + iter_index,
        finished_at=1.5 + iter_index,
    )


def _verifier_end(run_id: str, iterations: int, score: float, converged: bool) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="VerifierLoop",
        kind="algo_end",
        payload={"iterations": iterations, "score": score, "converged": converged},
        started_at=1.0,
        finished_at=2.0,
    )


def _selfrefine_iter_refine(run_id: str, iter_index: int) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="SelfRefine",
        kind="iteration",
        payload={"iter_index": iter_index, "phase": "refine"},
        started_at=1.0 + iter_index,
        finished_at=1.5 + iter_index,
    )


def _selfrefine_iter_reflect(
    run_id: str, iter_index: int, needs_revision: bool, critique_summary: str
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="SelfRefine",
        kind="iteration",
        payload={
            "iter_index": iter_index,
            "phase": "reflect",
            "needs_revision": needs_revision,
            "critique_summary": critique_summary,
        },
        started_at=1.0 + iter_index,
        finished_at=1.5 + iter_index,
    )


def test_iterations_json_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/iterations.json").status_code == 404


async def test_iterations_json_verifier_loop(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(_verifier_start("r1", max_iter=5, threshold=0.8))
    await obs.on_event(_verifier_iter("r1", 0, 0.5))
    await obs.on_event(_verifier_iter("r1", 1, 0.75))
    await obs.on_event(_verifier_iter("r1", 2, 0.9))
    await obs.on_event(_verifier_end("r1", iterations=3, score=0.9, converged=True))

    with TestClient(app) as client:
        resp = client.get("/runs/r1/iterations.json").json()

    assert resp["max_iter"] == 5
    assert abs(resp["threshold"] - 0.8) < 1e-9
    assert resp["converged"] is True
    iters = resp["iterations"]
    assert len(iters) == 3
    assert [it["iter_index"] for it in iters] == [0, 1, 2]
    assert all(it["phase"] == "verify" for it in iters)
    assert iters[2]["score"] == pytest.approx(0.9)


async def test_iterations_json_selfrefine(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    await obs.on_event(_selfrefine_iter_refine("r2", 1))
    await obs.on_event(_selfrefine_iter_reflect("r2", 0, needs_revision=True, critique_summary="too vague"))
    await obs.on_event(_selfrefine_iter_reflect("r2", 1, needs_revision=False, critique_summary="looks good"))

    with TestClient(app) as client:
        resp = client.get("/runs/r2/iterations.json").json()

    assert resp["threshold"] is None
    assert resp["max_iter"] is None
    iters = resp["iterations"]
    phases = [it["phase"] for it in iters]
    assert "refine" in phases
    assert "reflect" in phases
    # critique_summary lands in metadata
    reflect_iters = [it for it in iters if it["phase"] == "reflect"]
    assert reflect_iters[0]["metadata"]["critique_summary"] == "too vague"


async def test_iterations_json_empty_run(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r3")
    with TestClient(app) as client:
        resp = client.get("/runs/r3/iterations.json").json()
    assert resp["iterations"] == []
    assert resp["threshold"] is None
    assert resp["converged"] is None
