"""`/runs/{run_id}/debate.{json,sse}` — per-round proposals, critiques, scores."""

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


def _round_event(run_id: str, round_index: int) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Debate",
        kind="round",
        payload={
            "round_index": round_index,
            "proposals": [
                {"content": f"proposal A round {round_index}", "author": "alice"},
                {"content": f"proposal B round {round_index}", "author": "bob"},
            ],
            "critiques": [
                {"target_author": "alice", "comments": "good point", "score": 0.7},
                {"target_author": "bob", "comments": "weak argument", "score": 0.4},
            ],
            "scores": [0.7, 0.4],
        },
        started_at=1.0 + round_index,
        finished_at=1.5 + round_index,
    )


async def _push(obs: WebDashboardObserver, events) -> None:
    for ev in events:
        await obs.on_event(ev)


def test_debate_json_404_for_unknown(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/debate.json").status_code == 404


async def test_debate_json_two_rounds(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run(obs, "r1")
    await _push(obs, [_round_event("r1", 0), _round_event("r1", 1)])
    with TestClient(app) as client:
        r = client.get("/runs/r1/debate.json")
        assert r.status_code == 200
        rounds = r.json()
        assert len(rounds) == 2
        assert [rd["round_index"] for rd in rounds] == [0, 1]
        assert rounds[0]["scores"] == pytest.approx([0.7, 0.4])
        assert rounds[0]["proposals"][0]["author"] == "alice"
        assert rounds[0]["critiques"][0]["comments"] == "good point"


async def test_debate_json_empty_run(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run(obs, "r2")
    with TestClient(app) as client:
        r = client.get("/runs/r2/debate.json")
        assert r.status_code == 200
        assert r.json() == []


async def test_debate_json_ignores_other_algo_events(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed_run(obs, "r3")
    noise = AlgorithmEvent(
        run_id="r3",
        algorithm_path="EvoGradient",
        kind="round",
        payload={"round_index": 0, "proposals": [], "critiques": [], "scores": []},
        started_at=1.0,
        finished_at=1.1,
    )
    await obs.on_event(noise)
    await obs.on_event(_round_event("r3", 0))
    with TestClient(app) as client:
        rounds = client.get("/runs/r3/debate.json").json()
        assert len(rounds) == 1
        assert rounds[0]["proposals"][0]["author"] == "alice"


async def test_debate_sse_replays_history(app_and_obs) -> None:
    from operad_dashboard.routes import per_run_sse
    from operad_dashboard.routes.debate import _to_entry

    _, obs = app_and_obs
    _seed_run(obs, "r4")
    await obs.on_event(_round_event("r4", 0))

    class _FakeRequest:
        async def is_disconnected(self) -> bool:
            return True

    gen = per_run_sse(
        _FakeRequest(),  # type: ignore[arg-type]
        obs,
        "r4",
        event_type="algo_event",
        kind="round",
        algorithm_path="Debate",
        transform=_to_entry,
    )
    chunks: list[dict] = []
    async for chunk in gen:
        chunks.append(chunk)
    assert chunks, "expected at least one replayed envelope"
    payload = json.loads(chunks[0]["data"])
    assert payload["round_index"] == 0
    assert payload["scores"] == pytest.approx([0.7, 0.4])
