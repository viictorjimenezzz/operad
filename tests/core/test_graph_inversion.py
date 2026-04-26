"""Tests for `operad.core.graph.to_io_graph`."""

from __future__ import annotations

import json
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from operad import Parallel, Pipeline
from operad.agents.reasoning.switch import Switch
from operad.core.graph import to_io_graph

from tests.conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


class _LeafIn(BaseModel):
    question: str = Field(default="", description="User question.")
    system_hint: str = Field(
        default="",
        description="Private instruction.",
        json_schema_extra={"operad": {"system": True}},
    )
    no_desc: int = 0


class _LeafOut(BaseModel):
    answer: str = Field(default="", description="Final answer.")


class _Route(BaseModel):
    label: Literal["in", "out"] = "in"


class _ParOut(BaseModel):
    left: int = 0
    right: str = ""


def _node_by_name(data: dict, name: str) -> dict:
    for node in data["nodes"]:
        if node["name"] == name:
            return node
    raise AssertionError(f"missing node {name!r}")


async def test_to_io_graph_leaf_emits_one_edge_two_nodes(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    data = to_io_graph(leaf._graph)
    assert data["root"] == "FakeLeaf"
    assert len(data["edges"]) == 1
    assert len(data["nodes"]) == 2
    edge = data["edges"][0]
    assert edge["agent_path"] == "FakeLeaf"
    assert edge["composite_path"] is None


async def test_to_io_graph_pipeline_dedupes_shared_type_nodes(cfg) -> None:
    p = Pipeline(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        FakeLeaf(config=cfg, input=C, output=B),
        input=A,
        output=B,
    )
    await p.abuild()
    data = to_io_graph(p._graph)
    assert len(data["edges"]) == 3
    assert len(data["nodes"]) == 3
    assert {e["agent_path"] for e in data["edges"]} == {
        "Pipeline.stage_0",
        "Pipeline.stage_1",
        "Pipeline.stage_2",
    }


async def test_to_io_graph_parallel_has_two_leaf_edges(cfg) -> None:
    parallel = Parallel(
        {
            "left": FakeLeaf(config=cfg, input=A, output=B),
            "right": FakeLeaf(config=cfg, input=A, output=C),
        },
        input=A,
        output=_ParOut,
        combine=lambda xs: _ParOut(
            left=xs["left"].value,
            right=xs["right"].label,
        ),
    )
    await parallel.abuild()
    data = to_io_graph(parallel._graph)
    assert len(data["edges"]) == 2
    assert {e["agent_path"] for e in data["edges"]} == {
        "Parallel.left",
        "Parallel.right",
    }


async def test_to_io_graph_switch_includes_router_and_branches(cfg) -> None:
    switch = Switch(
        router=FakeLeaf(config=cfg, input=A, output=_Route),
        branches={
            "in": FakeLeaf(config=cfg, input=A, output=B),
            "out": FakeLeaf(config=cfg, input=A, output=B),
        },
        input=A,
        output=B,
    )
    await switch.abuild()
    data = to_io_graph(switch._graph)
    assert len(data["edges"]) == 3
    assert {e["agent_path"] for e in data["edges"]} == {
        "Switch.router",
        "Switch.branch_in",
        "Switch.branch_out",
    }


async def test_to_io_graph_includes_field_metadata_and_system_flag(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=_LeafIn, output=_LeafOut).abuild()
    data = to_io_graph(leaf._graph)
    in_node = _node_by_name(data, "_LeafIn")
    question = next(f for f in in_node["fields"] if f["name"] == "question")
    system_hint = next(f for f in in_node["fields"] if f["name"] == "system_hint")
    no_desc = next(f for f in in_node["fields"] if f["name"] == "no_desc")
    assert question["description"] == "User question."
    assert question["system"] is False
    assert system_hint["system"] is True
    assert no_desc["description"] == ""


async def test_to_io_graph_json_serializable(cfg) -> None:
    p = Pipeline(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    await p.abuild()
    data = to_io_graph(p._graph)
    assert json.loads(json.dumps(data)) == data
