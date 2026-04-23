"""Tests for `Trace` + `TraceObserver`: capture, save/load, graph round-trip."""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent, Trace, TraceObserver, TypeRegistry
from operad.runtime.observers import base as _obs

from tests.conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    _obs.registry.clear()
    yield
    _obs.registry.clear()


async def test_trace_observer_captures_leaf_run(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 9}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)

    await leaf(A(text="hi"))

    t = obs.last()
    assert t is not None
    assert len(t.steps) == 1
    assert t.steps[0].agent_path == "FakeLeaf"
    assert t.steps[0].output.response.value == 9
    assert t.root_input == {"text": "hi"}
    assert t.root_output == {"value": 9}
    assert t.graph  # graph dict populated


async def test_trace_observer_captures_composite_in_order(cfg) -> None:
    class Chain(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2})
            self.second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})

        async def forward(self, x: A) -> C:
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    chain = await Chain().abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)

    await chain(A(text="go"))

    t = obs.last()
    assert t is not None
    paths = [s.agent_path for s in t.steps]
    # End events fire in reverse-finish order: children finish before parent.
    assert "Chain" in paths
    assert "Chain.first" in paths
    assert "Chain.second" in paths
    assert t.root_output == {"label": "ok"}


async def test_trace_save_load_json_roundtrips(cfg, tmp_path) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 5}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    await leaf(A(text="rt"))

    t = obs.last()
    assert t is not None
    path = tmp_path / "trace.json"
    t.save(path)
    loaded = Trace.load(path)
    assert loaded.model_dump(mode="json") == t.model_dump(mode="json")


async def test_trace_save_load_ndjson_roundtrips(cfg, tmp_path) -> None:
    class Chain(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2})
            self.second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "x"})

        async def forward(self, x: A) -> C:
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    chain = await Chain().abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    await chain(A(text="nd"))

    t = obs.last()
    assert t is not None
    path = tmp_path / "trace.ndjson"
    t.save(path, ndjson=True)
    loaded = Trace.load(path)
    assert loaded.model_dump(mode="json") == t.model_dump(mode="json")


async def test_trace_graph_rehydrates_with_registry(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    await leaf(A(text="g"))

    t = obs.last()
    assert t is not None
    reg = TypeRegistry()
    # tests.conftest isn't importable via module path on all layouts;
    # register explicitly for determinism.
    reg.register(A)
    reg.register(B)
    g = t.rehydrate_graph(reg)
    assert g.root
    assert g.nodes


async def test_trace_captures_error_run(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    async def boom(x: A) -> B:
        raise ValueError("kaboom")

    leaf.forward = boom  # type: ignore[method-assign]
    obs = TraceObserver()
    _obs.registry.register(obs)

    with pytest.raises(ValueError):
        await leaf(A(text="fail"))

    t = obs.last()
    assert t is not None
    assert t.error and "kaboom" in t.error
