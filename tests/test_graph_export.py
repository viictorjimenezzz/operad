"""Tests for `operad.core.graph` exporters."""

from __future__ import annotations

import pytest

from operad import Pipeline
from operad.core.graph import to_json, to_mermaid

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def _built_pipeline(cfg):
    first = FakeLeaf(config=cfg, input=A, output=B)
    second = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(first, second, input=A, output=C)
    await p.abuild()
    return p


async def test_to_mermaid_contains_nodes_and_edges(cfg) -> None:
    p = await _built_pipeline(cfg)
    text = to_mermaid(p._graph)
    assert text.splitlines()[0] == "flowchart LR"
    assert "Pipeline_stage_0" in text
    assert "Pipeline_stage_1" in text
    assert "A -> B" in text and "B -> C" in text


async def test_to_json_is_serializable(cfg) -> None:
    import json

    p = await _built_pipeline(cfg)
    data = to_json(p._graph)
    assert json.loads(json.dumps(data)) == data
    assert data["root"] == "Pipeline"
    paths = [n["path"] for n in data["nodes"]]
    assert "Pipeline" in paths
    assert "Pipeline.stage_0" in paths
    assert "Pipeline.stage_1" in paths
    kinds = {n["path"]: n["kind"] for n in data["nodes"]}
    assert kinds["Pipeline"] == "composite"
    assert kinds["Pipeline.stage_0"] == "leaf"
