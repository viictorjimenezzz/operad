"""Tests for `operad.core.graph` exporters."""

from __future__ import annotations

import pytest

from operad import Agent, Sequential
from operad.agents import Loop
from operad.core.graph import to_json, to_mermaid

from ..conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def _built_pipeline(cfg):
    first = FakeLeaf(config=cfg, input=A, output=B)
    second = FakeLeaf(config=cfg, input=B, output=C)
    p = Sequential(first, second, input=A, output=C)
    await p.abuild()
    return p


async def test_to_mermaid_contains_nodes_and_edges(cfg) -> None:
    p = await _built_pipeline(cfg)
    text = to_mermaid(p._graph)
    assert text.splitlines()[0] == "flowchart LR"
    assert "Sequential_stage_0" in text
    assert "Sequential_stage_1" in text
    assert "A -> B" in text and "B -> C" in text
    assert "classDef pipelineSequential" in text


async def test_to_mermaid_dedupes_repeated_loop_stage(cfg) -> None:
    stage = FakeLeaf(config=cfg, input=A, output=A)
    loop = Loop(stage, input=A, output=A, n_loops=2)
    await loop.abuild()

    text = to_mermaid(loop._graph)
    # Loop traces the body twice; mermaid should still render one stage node.
    assert text.count('Loop_stage_0(("') == 1
    assert "classDef pipelineLoop" in text


async def test_to_mermaid_pipeline_label_shows_class_name(cfg) -> None:
    class _Wrapper(Agent[A, C]):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.pipeline = Sequential(
                FakeLeaf(config=cfg, input=A, output=B),
                FakeLeaf(config=cfg, input=B, output=C),
                input=A,
                output=C,
            )

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return (await self.pipeline(x)).response

    root = _Wrapper()
    await root.abuild()
    text = to_mermaid(root._graph)
    assert "Sequential<br/>_Wrapper.pipeline" in text


async def test_to_json_is_serializable(cfg) -> None:
    import json

    p = await _built_pipeline(cfg)
    data = to_json(p._graph)
    assert json.loads(json.dumps(data)) == data
    assert data["root"] == "Sequential"
    paths = [n["path"] for n in data["nodes"]]
    assert "Sequential" in paths
    assert "Sequential.stage_0" in paths
    assert "Sequential.stage_1" in paths
    kinds = {n["path"]: n["kind"] for n in data["nodes"]}
    assert kinds["Sequential"] == "composite"
    assert kinds["Sequential.stage_0"] == "leaf"
