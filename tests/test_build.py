"""Tests for `build_agent`: graph capture, type checks, rebuild behavior."""

from __future__ import annotations

import pytest

from operad import Agent, AgentGraph, BuildError

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_leaf_build_produces_empty_graph(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    g: AgentGraph = leaf._graph
    assert g.root == "FakeLeaf"
    assert [n.path for n in g.nodes] == ["FakeLeaf"]
    assert g.nodes[0].kind == "leaf"
    assert g.nodes[0].input_type is A and g.nodes[0].output_type is B
    assert g.edges == []


async def test_pipeline_build_captures_edges(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            mid = await self.first(x)
            return await self.second(mid)

    p = await Pipeline().abuild()
    g: AgentGraph = p._graph
    assert g.root == "Pipeline"
    assert len(g.edges) == 2

    e1, e2 = g.edges
    assert e1.caller == "Pipeline" and e1.callee == "Pipeline.first"
    assert e1.input_type is A and e1.output_type is B
    assert e2.caller == "Pipeline" and e2.callee == "Pipeline.second"
    assert e2.input_type is B and e2.output_type is C


async def test_build_catches_edge_input_mismatch_before_llm(cfg) -> None:
    class Wrong(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            # second expects B but we'll pass A into it
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            await self.first(x)
            return await self.second(x)  # type: ignore[arg-type]

    with pytest.raises(BuildError) as exc:
        await Wrong().abuild()
    assert exc.value.reason == "input_mismatch"
    assert exc.value.agent is not None and "second" in exc.value.agent


async def test_build_catches_root_output_mismatch(cfg) -> None:
    class BadRoot(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.only = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            # Returns a B but declared Out is C.
            return await self.only(x)  # type: ignore[return-value]

    with pytest.raises(BuildError) as exc:
        await BadRoot().abuild()
    assert exc.value.reason == "output_mismatch"


async def test_build_is_idempotent_after_mutation(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return await self.second(await self.first(x))

    p = await Pipeline().abuild()
    assert p._built is True

    p.first.task = "updated"
    p.first.config.temperature = 0.0
    await p.abuild()
    assert p._built is True
    assert p.first.task == "updated"


async def test_build_marks_all_descendants_built(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return await self.second(await self.first(x))

    p = await Pipeline().abuild()
    assert p._built is True
    assert p.first._built is True
    assert p.second._built is True


async def test_build_requires_input_output(cfg) -> None:
    class NoTypesLeaf(Agent):
        pass  # no class-level input/output

    with pytest.raises(BuildError) as exc:
        NoTypesLeaf(config=cfg)
    assert exc.value.reason == "prompt_incomplete"
