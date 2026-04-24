"""Observer-side coverage of the AlgorithmEvent path.

The dispatch contract: every existing observer must accept both event
types without raising. We assert this directly per observer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import (
    AgentEvent,
    Event,
    JsonlObserver,
    emit_algorithm_event,
)
from operad.runtime.observers import registry as obs_registry
from operad.runtime.observers.base import _enter_algorithm_run


pytestmark = pytest.mark.asyncio


class _Collector:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def on_event(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


def _make_algo_event(kind: str = "generation", run_id: str = "r1") -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id=run_id,
        algorithm_path="Demo",
        kind=kind,  # type: ignore[arg-type]
        payload={"gen_index": 0, "population_scores": [0.1, 0.9], "extra": "ignored"},
        started_at=1.0,
        finished_at=2.0,
    )


async def test_emit_algorithm_event_uses_run_id_from_context() -> None:
    col = _Collector()
    obs_registry.register(col)
    with _enter_algorithm_run() as rid:
        await emit_algorithm_event(
            "algo_start", algorithm_path="X", payload={"n": 1}
        )
    assert len(col.events) == 1
    assert isinstance(col.events[0], AlgorithmEvent)
    assert col.events[0].run_id == rid
    assert col.events[0].kind == "algo_start"


async def test_emit_algorithm_event_reuses_outer_run_id() -> None:
    col = _Collector()
    obs_registry.register(col)
    with _enter_algorithm_run() as outer:
        with _enter_algorithm_run() as inner:
            await emit_algorithm_event(
                "algo_start", algorithm_path="Inner", payload={}
            )
    assert outer == inner
    assert col.events[0].run_id == outer


async def test_jsonl_observer_handles_algorithm_event(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    jo = JsonlObserver(log)
    try:
        await jo.on_event(_make_algo_event("algo_start"))
        await jo.on_event(_make_algo_event("generation"))
        await jo.on_event(_make_algo_event("algo_end"))
    finally:
        jo.close()

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert [r["kind"] for r in records] == ["algo_start", "generation", "algo_end"]
    assert all(r["event"] == "algorithm" for r in records)
    assert all(r["algorithm_path"] == "Demo" for r in records)
    # Unknown payload keys round-trip without raising.
    assert records[1]["payload"]["extra"] == "ignored"


async def test_jsonl_observer_still_handles_agent_event(tmp_path: Path) -> None:
    log = tmp_path / "mixed.jsonl"
    jo = JsonlObserver(log)
    try:
        await jo.on_event(
            AgentEvent(
                run_id="r1",
                agent_path="Leaf",
                kind="start",
                input=None,
                output=None,
                error=None,
                started_at=1.0,
                finished_at=None,
            )
        )
        await jo.on_event(_make_algo_event("algo_start"))
    finally:
        jo.close()

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert records[0]["event"] == "agent"
    assert records[1]["event"] == "algorithm"


async def test_rich_observer_handles_algorithm_event() -> None:
    pytest.importorskip("rich")
    from operad.runtime.observers import RichDashboardObserver

    obs = RichDashboardObserver()
    try:
        await obs.on_event(_make_algo_event("algo_start"))
        await obs.on_event(_make_algo_event("generation"))
        await obs.on_event(_make_algo_event("algo_end"))
        # Mixing in an AgentEvent must not break the tree.
        await obs.on_event(
            AgentEvent(
                run_id="r1",
                agent_path="Leaf",
                kind="start",
                input=None,
                output=None,
                error=None,
                started_at=1.0,
                finished_at=None,
            )
        )
    finally:
        obs.stop()


async def test_otel_observer_handles_algorithm_event() -> None:
    pytest.importorskip("opentelemetry")
    from operad.runtime.observers import OtelObserver

    obs = OtelObserver()
    await obs.on_event(_make_algo_event("algo_start"))
    await obs.on_event(_make_algo_event("generation"))
    await obs.on_event(_make_algo_event("algo_end"))
    # algo_error after a fresh run also closes a span cleanly.
    await obs.on_event(
        AlgorithmEvent(
            run_id="r2",
            algorithm_path="Other",
            kind="algo_error",
            payload={"type": "ValueError", "message": "boom"},
            started_at=1.0,
            finished_at=2.0,
        )
    )
