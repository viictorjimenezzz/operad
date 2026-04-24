"""WebDashboardObserver event ingestion + per-subscriber fan-out."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import AgentEvent

from operad_dashboard.observer import (
    WebDashboardObserver,
    _put_drop_oldest,
    serialize_event,
)


class _Out(BaseModel):
    text: str = "hi"


def _agent_event(run_id: str = "r1", kind: str = "start", **meta: Any) -> AgentEvent:
    return AgentEvent(
        run_id=run_id,
        agent_path="Pipeline",
        kind=kind,  # type: ignore[arg-type]
        input=None,
        output=_Out() if kind == "end" else None,
        error=None,
        started_at=1700000000.0,
        finished_at=None if kind == "start" else 1700000001.0,
        metadata=meta or {},
    )


def _algo_event(run_id: str = "r1", kind: str = "algo_start") -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Evolutionary",
        kind=kind,  # type: ignore[arg-type]
        payload={"n": 4},
        started_at=1700000000.0,
        finished_at=None,
    )


async def test_serialize_agent_event_strips_graph_metadata() -> None:
    big_graph = {"root": "X", "nodes": [{"path": "X"}], "edges": []}
    env = serialize_event(_agent_event(kind="end", graph=big_graph, is_root=True))
    assert env["type"] == "agent_event"
    assert env["metadata"]["graph"] == "<cached at /graph/{run_id}>"
    assert env["metadata"]["is_root"] is True
    assert env["output"] == {"text": "hi"}


async def test_serialize_algorithm_event() -> None:
    env = serialize_event(_algo_event(kind="generation"))
    assert env["type"] == "algo_event"
    assert env["algorithm_path"] == "Evolutionary"
    assert env["payload"] == {"n": 4}


async def test_fanout_to_two_subscribers() -> None:
    obs = WebDashboardObserver()
    q1 = obs.subscribe()
    q2 = obs.subscribe()
    await obs.on_event(_agent_event())
    e1 = await asyncio.wait_for(q1.get(), timeout=0.1)
    e2 = await asyncio.wait_for(q2.get(), timeout=0.1)
    assert e1 == e2
    assert e1["run_id"] == "r1"


async def test_drop_oldest_on_overflow() -> None:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
    _put_drop_oldest(q, {"i": 0})
    _put_drop_oldest(q, {"i": 1})
    _put_drop_oldest(q, {"i": 2})
    items = [q.get_nowait(), q.get_nowait()]
    assert [it["i"] for it in items] == [1, 2]


async def test_run_registry_tracks_state_transitions() -> None:
    obs = WebDashboardObserver()
    await obs.on_event(_agent_event(kind="start", is_root=True))
    info = obs.registry.get("r1")
    assert info is not None and info.state == "running"
    await obs.on_event(_agent_event(kind="end", is_root=True))
    assert obs.registry.get("r1").state == "ended"


async def test_unsubscribe_stops_delivery() -> None:
    obs = WebDashboardObserver()
    q = obs.subscribe()
    obs.unsubscribe(q)
    await obs.on_event(_agent_event())
    with pytest.raises(asyncio.QueueEmpty):
        q.get_nowait()
