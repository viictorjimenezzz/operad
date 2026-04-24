"""Observer protocol tests: events, isolation, tracing, JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from operad import Agent
from operad.runtime.observers import AgentEvent, JsonlObserver
from operad.runtime.observers import registry as obs_registry

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


class _Collector:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def on_event(self, event: AgentEvent) -> None:
        self.events.append(event)


class _Exploder:
    def __init__(self) -> None:
        self.calls = 0

    async def on_event(self, event: AgentEvent) -> None:
        self.calls += 1
        raise RuntimeError("observer boom")


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


async def test_leaf_emits_start_then_end(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7}).abuild()

    col = _Collector()
    obs_registry.register(col)

    out = await leaf(A(text="hi"))
    assert out.response.value == 7

    assert [e.kind for e in col.events] == ["start", "end"]
    assert col.events[0].agent_path == "FakeLeaf"
    assert col.events[1].agent_path == "FakeLeaf"
    assert col.events[0].input.text == "hi"
    assert col.events[1].output.response.value == 7
    assert col.events[0].run_id == col.events[1].run_id
    assert col.events[1].finished_at is not None


async def test_error_in_forward_emits_start_then_error(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    async def boom(x: A) -> B:
        raise ValueError("kaboom")

    leaf.forward = boom  # type: ignore[method-assign]

    col = _Collector()
    obs_registry.register(col)

    with pytest.raises(ValueError):
        await leaf(A())

    kinds = [e.kind for e in col.events]
    assert kinds == ["start", "error"]
    err_event = col.events[-1]
    assert isinstance(err_event.error, ValueError)


async def test_observer_exception_is_isolated(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    bad = _Exploder()
    good = _Collector()
    obs_registry.register(bad)
    obs_registry.register(good)

    out = await leaf(A())
    assert isinstance(out.response, B)
    assert bad.calls >= 1
    assert [e.kind for e in good.events] == ["start", "end"]


async def test_no_events_during_build(cfg) -> None:
    col = _Collector()
    obs_registry.register(col)

    class Tree(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    await Tree().abuild()

    assert col.events == []


async def test_jsonl_observer_round_trip(tmp_path: Path, cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 3}).abuild()

    log = tmp_path / "events.jsonl"
    jo = JsonlObserver(log)
    obs_registry.register(jo)
    try:
        await leaf(A(text="abc"))
    finally:
        jo.close()

    lines = log.read_text().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert [r["kind"] for r in records] == ["start", "end"]
    assert records[0]["run_id"] == records[1]["run_id"]
    assert records[0]["input"] == {"text": "abc"}
    assert records[1]["output"]["response"] == {"value": 3}
    assert records[0]["agent_path"] == "FakeLeaf"


async def test_nested_composite_dotted_paths(cfg) -> None:
    class Chain(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 1}
            )
            self.second = FakeLeaf(
                config=cfg, input=B, output=C, canned={"label": "ok"}
            )

        async def forward(self, x: A) -> C:  # type: ignore[override]
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    chain = await Chain().abuild()
    col = _Collector()
    obs_registry.register(col)

    await chain(A())

    paths = [(e.agent_path, e.kind) for e in col.events]
    assert ("Chain", "start") in paths
    assert ("Chain.first", "start") in paths
    assert ("Chain.first", "end") in paths
    assert ("Chain.second", "start") in paths
    assert ("Chain.second", "end") in paths
    assert ("Chain", "end") in paths


async def test_shared_run_id_across_children(cfg) -> None:
    class Chain(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.only = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 5}
            )

        async def forward(self, x: A) -> B:  # type: ignore[override]
            return (await self.only(x)).response

    chain = await Chain().abuild()
    col = _Collector()
    obs_registry.register(col)

    await chain(A())

    run_ids = {e.run_id for e in col.events}
    assert len(run_ids) == 1
