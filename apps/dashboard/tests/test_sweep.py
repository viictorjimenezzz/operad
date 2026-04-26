"""`/runs/{run_id}/sweep.{json,sse}` — Sweep aggregation route tests."""

from __future__ import annotations

from collections import deque

import pytest
from fastapi.testclient import TestClient

from operad.runtime.events import AlgorithmEvent
from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver
from operad_dashboard.routes.sweep import _compute_snapshot
from operad_dashboard.runs import RunInfo


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def _seed(obs: WebDashboardObserver, run_id: str) -> None:
    obs.registry._runs[run_id] = RunInfo(  # type: ignore[attr-defined]
        run_id=run_id,
        started_at=0.0,
        last_event_at=0.0,
        state="running",
        events=deque(maxlen=1000),
    )


def _cell(run_id: str, idx: int, params: dict, score: float | None) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Sweep",
        kind="cell",
        payload={"cell_index": idx, "parameters": params, "score": score},
        started_at=0.0,
        finished_at=0.0,
    )


def _end(run_id: str, cells: int) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Sweep",
        kind="algo_end",
        payload={"cells": cells},
        started_at=0.0,
        finished_at=1.0,
    )


# ---------------------------------------------------------------------------
# _compute_snapshot unit tests
# ---------------------------------------------------------------------------


def _env(kind: str, payload: dict, algorithm_path: str = "Sweep") -> dict:
    return {
        "type": "algo_event",
        "algorithm_path": algorithm_path,
        "kind": kind,
        "payload": payload,
        "started_at": 0.0,
        "finished_at": 1.0,
        "metadata": {},
    }


def test_compute_snapshot_2d_axes() -> None:
    events = [
        _env("cell", {"cell_index": 0, "parameters": {"temp": 0.5, "tok": 100}, "score": 0.7}),
        _env("cell", {"cell_index": 1, "parameters": {"temp": 0.5, "tok": 200}, "score": 0.8}),
        _env("cell", {"cell_index": 2, "parameters": {"temp": 1.0, "tok": 100}, "score": 0.5}),
        _env("cell", {"cell_index": 3, "parameters": {"temp": 1.0, "tok": 200}, "score": 0.9}),
        _env("algo_end", {"cells": 4}),
    ]
    snap = _compute_snapshot(iter(events))

    assert len(snap["cells"]) == 4
    axis_names = [a["name"] for a in snap["axes"]]
    assert axis_names == ["temp", "tok"]
    temp_axis = next(a for a in snap["axes"] if a["name"] == "temp")
    assert temp_axis["values"] == [0.5, 1.0]
    assert snap["best_cell_index"] == 3
    assert snap["score_range"] == [0.5, 0.9]
    assert snap["finished"] is True
    assert snap["total_cells"] == 4


def test_compute_snapshot_none_scores() -> None:
    events = [
        _env("cell", {"cell_index": 0, "parameters": {"x": 1}, "score": None}),
        _env("cell", {"cell_index": 1, "parameters": {"x": 2}, "score": None}),
        _env("algo_end", {"cells": 2}),
    ]
    snap = _compute_snapshot(iter(events))

    assert snap["score_range"] is None
    assert snap["best_cell_index"] is None
    assert snap["finished"] is True


def test_compute_snapshot_empty() -> None:
    snap = _compute_snapshot(iter([]))
    assert snap["cells"] == []
    assert snap["axes"] == []
    assert snap["score_range"] is None
    assert snap["finished"] is False


def test_compute_snapshot_ignores_other_algorithms() -> None:
    events = [
        _env("cell", {"cell_index": 0, "parameters": {"x": 1}, "score": 0.9}, algorithm_path="EvoGradient"),
    ]
    snap = _compute_snapshot(iter(events))
    assert snap["cells"] == []


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


async def test_sweep_json_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        assert client.get("/runs/nope/sweep.json").status_code == 404


async def test_sweep_json_2d_grid(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r1")
    await obs.on_event(_cell("r1", 0, {"temperature": 0.5, "max_tokens": 100}, 0.7))
    await obs.on_event(_cell("r1", 1, {"temperature": 0.5, "max_tokens": 200}, 0.8))
    await obs.on_event(_cell("r1", 2, {"temperature": 1.0, "max_tokens": 100}, 0.5))
    await obs.on_event(_cell("r1", 3, {"temperature": 1.0, "max_tokens": 200}, 0.9))
    await obs.on_event(_end("r1", 4))

    with TestClient(app) as client:
        data = client.get("/runs/r1/sweep.json").json()

    assert len(data["cells"]) == 4
    assert data["best_cell_index"] == 3
    assert data["score_range"] == [0.5, 0.9]
    assert data["finished"] is True
    axis_names = [a["name"] for a in data["axes"]]
    assert "temperature" in axis_names
    assert "max_tokens" in axis_names


async def test_sweep_json_null_scores(app_and_obs) -> None:
    app, obs = app_and_obs
    _seed(obs, "r2")
    await obs.on_event(_cell("r2", 0, {"x": 1}, None))
    await obs.on_event(_cell("r2", 1, {"x": 2}, None))
    await obs.on_event(_end("r2", 2))

    with TestClient(app) as client:
        data = client.get("/runs/r2/sweep.json").json()

    assert data["score_range"] is None
    assert data["best_cell_index"] is None
