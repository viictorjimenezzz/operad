"""Tests for inverted IO graph export (`to_io_graph`)."""

from __future__ import annotations

import json
from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field

from operad import Agent, Parallel, Sequential
from operad.agents import Choice, RouteClassifier, Router
from operad.core.view import to_io_graph, to_io_graph_from_json, to_json

from ..conftest import A, B, C, D, FakeLeaf


pytestmark = pytest.mark.asyncio


def _q(t: type) -> str:
    module = getattr(t, "__module__", "") or ""
    qualname = getattr(t, "__qualname__", None) or getattr(t, "__name__", "")
    return f"{module}.{qualname}" if module else qualname


class Label(Choice[Literal["in", "out"]]):
    pass


class _StubRouter(RouteClassifier):
    def __init__(self) -> None:
        super().__init__(config=None, input=A, output=Label)

    async def forward(self, x: Any) -> Any:
        return Label.model_construct(label="in", reasoning="stub")


class _Branch(Agent[A, B]):
    input = A
    output = B

    def __init__(self, *, tag: str) -> None:
        super().__init__(config=None, input=A, output=B)
        self.tag = tag

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=1 if self.tag == "in" else 2)


class RichIn(BaseModel):
    context: str = Field(
        default="",
        description="System context.",
        json_schema_extra={"operad": {"system": True}},
    )
    prompt: str = Field(default="")
    decision: Literal["accept", "reject"] = Field(
        default="accept",
        description="Routing decision.",
    )


class RichOut(BaseModel):
    answer: str = Field(default="ok", description="Output text.")


async def test_leaf_root_emits_one_edge_and_two_type_nodes(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    data = to_io_graph(leaf._graph)

    assert data["root"] == "FakeLeaf"
    assert len(data["edges"]) == 1
    assert {n["key"] for n in data["nodes"]} == {_q(A), _q(B)}

    edge = data["edges"][0]
    assert edge["agent_path"] == "FakeLeaf"
    assert edge["class_name"] == "FakeLeaf"
    assert edge["kind"] == "leaf"
    assert edge["from"] == _q(A)
    assert edge["to"] == _q(B)
    assert edge["composite_path"] is None


async def test_pipeline_inversion_has_three_edges_and_deduped_type_nodes(cfg) -> None:
    p = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await p.abuild()

    data = to_io_graph(p._graph)
    assert len(data["edges"]) == 3
    assert len(data["nodes"]) == 4
    assert {n["key"] for n in data["nodes"]} == {_q(A), _q(B), _q(C), _q(D)}
    assert all(e["composite_path"] is None for e in data["edges"])


async def test_parallel_inversion_fans_out_from_shared_input_type(cfg) -> None:
    p = Parallel(
        {
            "left": FakeLeaf(config=cfg, input=A, output=B),
            "right": FakeLeaf(config=cfg, input=A, output=C),
        },
        input=A,
        output=D,
        combine=lambda _: D.model_construct(payload=[]),
    )
    await p.abuild()

    data = to_io_graph(p._graph)
    assert len(data["edges"]) == 2
    assert {e["from"] for e in data["edges"]} == {_q(A)}
    assert {e["to"] for e in data["edges"]} == {_q(B), _q(C)}


async def test_switch_inversion_contains_router_and_branch_edges() -> None:
    s = Router(
        router=_StubRouter(),
        branches={"in": _Branch(tag="in"), "out": _Branch(tag="out")},
        input=A,
        output=B,
    )
    await s.abuild()

    data = to_io_graph(s._graph)
    assert len(data["edges"]) == 3
    assert {e["from"] for e in data["edges"]} == {_q(A)}
    class_names = {e["agent_path"]: e["class_name"] for e in data["edges"]}
    assert class_names["Router.router"] == "_StubRouter"
    assert class_names["Router.branch_in"] == "_Branch"
    assert class_names["Router.branch_out"] == "_Branch"


async def test_io_graph_field_metadata_includes_system_and_extended_fields(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=RichIn, output=RichOut).abuild()
    data = to_io_graph(leaf._graph)

    in_node = next(n for n in data["nodes"] if n["key"] == _q(RichIn))
    fields = {f["name"]: f for f in in_node["fields"]}

    assert fields["context"]["system"] is True
    assert fields["context"]["description"] == "System context."
    assert fields["prompt"]["description"] == ""
    assert fields["decision"]["type"] == "Literal['accept','reject']"
    assert fields["decision"]["enum_values"] == ["accept", "reject"]
    assert fields["context"]["required"] is False
    assert fields["context"]["has_default"] is True


async def test_to_io_graph_output_is_json_serializable(cfg) -> None:
    p = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    await p.abuild()

    data = to_io_graph(p._graph)
    assert json.loads(json.dumps(data)) == data


async def test_composite_path_uses_nearest_non_root_composite(cfg) -> None:
    inner = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    outer = Sequential(
        inner,
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await outer.abuild()

    data = to_io_graph(outer._graph)
    by_path = {e["agent_path"]: e for e in data["edges"]}

    assert by_path["Sequential.stage_0.stage_0"]["composite_path"] == "Sequential.stage_0"
    assert by_path["Sequential.stage_0.stage_1"]["composite_path"] == "Sequential.stage_0"
    assert by_path["Sequential.stage_1"]["composite_path"] is None


async def test_to_io_graph_from_json_matches_live_graph(cfg) -> None:
    """JSON-only inversion (used by the dashboard) matches the live walker."""
    p = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    await p.abuild()

    live = to_io_graph(p._graph)
    rehydrated = to_io_graph_from_json(to_json(p._graph))

    assert rehydrated["root"] == live["root"]
    assert {e["agent_path"] for e in rehydrated["edges"]} == {
        e["agent_path"] for e in live["edges"]
    }
    assert {n["key"] for n in rehydrated["nodes"]} == {n["key"] for n in live["nodes"]}

    rehydrated_fields = {n["key"]: [f["name"] for f in n["fields"]] for n in rehydrated["nodes"]}
    live_fields = {n["key"]: [f["name"] for f in n["fields"]] for n in live["nodes"]}
    assert rehydrated_fields == live_fields

    rehydrated_classes = {e["agent_path"]: e["class_name"] for e in rehydrated["edges"]}
    live_classes = {e["agent_path"]: e["class_name"] for e in live["edges"]}
    assert rehydrated_classes == live_classes


async def test_to_io_graph_from_json_handles_unimportable_types() -> None:
    """The dashboard receives graph_json from a different process; types
    referenced as ``__main__.Foo`` cannot be imported. Inversion must still
    produce edges and field metadata when those are embedded inline."""
    graph_json = {
        "root": "Sequential",
        "nodes": [
            {
                "path": "Sequential",
                "kind": "composite",
                "input": "__main__.Question",
                "output": "__main__.Answer",
                "class_name": "Sequential",
                "input_fields": [
                    {"name": "text", "type": "str", "description": "the question", "system": False},
                ],
                "output_fields": [
                    {"name": "answer", "type": "str", "description": "the answer", "system": False},
                ],
            },
            {
                "path": "Sequential.stage_0",
                "kind": "leaf",
                "input": "__main__.Question",
                "output": "__main__.Answer",
                "class_name": "MyLeaf",
                "input_fields": [
                    {"name": "text", "type": "str", "description": "the question", "system": False},
                ],
                "output_fields": [
                    {"name": "answer", "type": "str", "description": "the answer", "system": False},
                ],
            },
        ],
        "edges": [
            {
                "caller": "Sequential",
                "callee": "Sequential.stage_0",
                "input": "__main__.Question",
                "output": "__main__.Answer",
                "class_name": "MyLeaf",
            }
        ],
    }

    data = to_io_graph_from_json(graph_json)

    assert data["root"] == "Sequential"
    assert [e["class_name"] for e in data["edges"]] == ["MyLeaf"]
    assert {n["key"] for n in data["nodes"]} == {"__main__.Question", "__main__.Answer"}
    text_field = next(
        f for n in data["nodes"] if n["key"] == "__main__.Question" for f in n["fields"]
    )
    assert text_field["name"] == "text"
    assert text_field["description"] == "the question"


async def test_to_io_graph_emits_composites_with_children(cfg) -> None:
    """`composites` array carries class_name, parent_path, and children paths."""
    inner = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    outer = Sequential(
        inner,
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await outer.abuild()

    data = to_io_graph(outer._graph)
    assert "composites" in data
    composites = {c["path"]: c for c in data["composites"]}

    # Root (outer Sequential) is excluded; only inner Sequential remains.
    assert "Sequential" not in composites
    assert "Sequential.stage_0" in composites

    inner_entry = composites["Sequential.stage_0"]
    assert inner_entry["class_name"] == "Sequential"
    assert inner_entry["kind"] == "composite"
    # Inner's parent is the root (excluded), so parent_path is None.
    assert inner_entry["parent_path"] is None
    # Inner's children are its two FakeLeaf stages.
    assert set(inner_entry["children"]) == {
        "Sequential.stage_0.stage_0",
        "Sequential.stage_0.stage_1",
    }


async def test_to_io_graph_from_json_composites_match_live(cfg) -> None:
    """JSON-only IO graph emits the same composites as the live walker."""
    inner = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    outer = Sequential(
        inner,
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await outer.abuild()

    live = to_io_graph(outer._graph)
    rehydrated = to_io_graph_from_json(to_json(outer._graph))

    def _norm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda c: c["path"])

    assert _norm(live["composites"]) == _norm(rehydrated["composites"])


async def test_to_agent_graph_renders_agents_as_nodes(cfg) -> None:
    """`to_agent_graph` returns the agent-flow shape: agents are nodes, types are edge labels."""
    from operad.core.view import to_agent_graph, to_agent_graph_from_json

    inner = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    outer = Sequential(
        inner,
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await outer.abuild()

    live = to_agent_graph(outer._graph)
    rehydrated = to_agent_graph_from_json(to_json(outer._graph))

    # Agents-as-nodes: every Node from the AgentGraph appears as a node here.
    assert {n["path"] for n in live["nodes"]} == {n.path for n in outer._graph.nodes}
    # parent_path is computed for descendants of composites (excluding root).
    inner_kids = [n for n in live["nodes"] if n["parent_path"] == "Sequential.stage_0"]
    assert {n["path"] for n in inner_kids} == {
        "Sequential.stage_0.stage_0",
        "Sequential.stage_0.stage_1",
    }
    # Edges carry the type that flowed (input_type label).
    edge_types = {(e["caller"], e["callee"], e["type"]) for e in live["edges"]}
    assert any(callee == "Sequential.stage_0" and t == "A" for _, callee, t in edge_types)

    # JSON path matches.
    assert {n["path"] for n in rehydrated["nodes"]} == {n["path"] for n in live["nodes"]}
    assert {(e["caller"], e["callee"]) for e in rehydrated["edges"]} == {
        (e["caller"], e["callee"]) for e in live["edges"]
    }


async def test_to_mermaid_emits_subgraphs_for_composites(cfg) -> None:
    """`to_mermaid` wraps composites in `subgraph` blocks."""
    from operad.core.view import to_mermaid

    inner = Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    )
    outer = Sequential(
        inner,
        FakeLeaf(config=cfg, input=C, output=D),
        input=A,
        output=D,
    )
    await outer.abuild()

    text = to_mermaid(outer._graph)
    # Root composite is flat (no subgraph), inner composite gets a subgraph block.
    assert "subgraph Sequential_stage_0" in text
    assert "    end" in text
    assert text.startswith("flowchart LR")
