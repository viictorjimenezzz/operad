"""`/runs/{run_id}/fitness.{json,sse}` — best/mean/spread per generation."""

from __future__ import annotations

import json
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


def _seed_run(obs: WebDashboardObserver, run_id: str) -> None:
    obs.registry._runs[run_id] = RunInfo(  # type: ignore[attr-defined]
        run_id=run_id,
        started_at=1.0,
        last_event_at=2.0,
        state="running",
        events=deque(maxlen=1000),
    )


def _gen_event(run_id: str, gen_index: int, scores: list[float]) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="EvoGradient",
        kind="generation",
        payload={
            "gen_index": gen_index,
            "population_scores": scores,
            "op_success_counts": {},
            "op_attempt_counts": {},
        },
        started_at=1.0 + gen_index,
        finished_at=1.5 + gen_index,
    )


async def _push(obs: WebDashboardObserver, events) -> None:
    for ev in events:
        await obs.on_event(ev)


def test_fitness_json_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/fitness.json").status_code == 404


async def test_fitness_json_three_generations(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run(obs, "r1")
    await _push(obs, [
        _gen_event("r1", 0, [0.2, 0.4, 0.6]),
        _gen_event("r1", 1, [0.3, 0.5, 0.7]),
        _gen_event("r1", 2, [0.5, 0.7, 0.9]),
    ])
    with TestClient(app) as client:
        r = client.get("/runs/r1/fitness.json")
        assert r.status_code == 200
        entries = r.json()
        assert [e["gen_index"] for e in entries] == [0, 1, 2]
        assert entries[0]["best"] == pytest.approx(0.6)
        assert entries[0]["mean"] == pytest.approx(0.4)
        assert entries[0]["worst"] == pytest.approx(0.2)
        assert entries[2]["population_scores"] == [0.5, 0.7, 0.9]


async def test_fitness_json_skips_iteration_without_score(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run(obs, "r2")
    noisy = AlgorithmEvent(
        run_id="r2",
        algorithm_path="PromptDrift",
        kind="iteration",
        payload={"epoch": 0, "hash_before": "a", "hash_after": "b"},
        started_at=1.0, finished_at=1.1,
    )
    await obs.on_event(noisy)
    await _push(obs, [_gen_event("r2", 0, [0.1, 0.5])])
    with TestClient(app) as client:
        entries = client.get("/runs/r2/fitness.json").json()
        assert [e["gen_index"] for e in entries] == [0]


async def test_fitness_sse_replays_history(app_and_obs) -> None:
    """`per_run_sse` replays buffered envelopes before going live."""
    from operad_dashboard.routes import per_run_sse
    from operad_dashboard.routes.fitness import _GEN_KINDS, _transform_or_ping

    _, obs = app_and_obs
    _seed_run(obs, "r3")
    await obs.on_event(_gen_event("r3", 0, [0.3, 0.5, 0.7]))

    class _FakeRequest:
        async def is_disconnected(self) -> bool:
            return True

    gen = per_run_sse(
        _FakeRequest(),  # type: ignore[arg-type]
        obs,
        "r3",
        event_type="algo_event",
        kind=_GEN_KINDS,
        transform=_transform_or_ping,
    )
    chunks: list[dict] = []
    async for chunk in gen:
        chunks.append(chunk)
    assert chunks, "expected at least one replayed envelope"
    payload = json.loads(chunks[0]["data"])
    assert payload["best"] == pytest.approx(0.7)
    assert payload["mean"] == pytest.approx(0.5)
