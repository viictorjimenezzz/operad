"""Tests for `AgentState`, `state()`, `load_state()`, `clone()`, and `__repr__`.

Covers the contract described in `.conductor/1-B-agent-state.md`:
round-trip, clone independence, nested structure preservation, shared
children, shape-mismatch errors, rebuild-after-clone, strands-state skip
on default-forward leaves, and the `__repr__` shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent, AgentState, BuildError, Example, Pipeline

from .conftest import A, B, C, FakeLeaf


class _TwoRefs(Agent[Any, Any]):
    """Minimal composite that attaches the same child under two names."""

    input = A
    output = B

    def __init__(self, leaf: Agent[Any, Any]) -> None:
        super().__init__(config=None, input=A, output=B)
        self.first = leaf
        self.second = leaf

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return (await self.first(x)).response


class _DefaultForwardLeaf(Agent[Any, Any]):
    """A leaf that uses `Agent.forward` unchanged; hits the leaf branch of clone."""

    input = A
    output = B


# --- state() / load_state() round-trip --------------------------------------


def test_state_captures_declared_fields(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    leaf.role = "persona"
    leaf.rules = ["r1", "r2"]
    leaf.examples = [Example(input=A(text="x"), output=B(value=1))]

    s = leaf.state()

    assert isinstance(s, AgentState)
    assert s.class_name == "FakeLeaf"
    assert s.role == "persona"
    assert s.task == "v1"
    assert s.rules == ["r1", "r2"]
    assert s.input_type_name == "A"
    assert s.output_type_name == "B"
    assert s.examples == [{"input": {"text": "x"}, "output": {"value": 1}}]
    assert s.config is not None
    assert s.config.temperature == 0.0
    assert s.children == {}


def test_load_state_roundtrip_is_noop_on_field_values(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    leaf.role = "persona"
    leaf.rules = ["r1", "r2"]
    leaf.examples = [Example(input=A(text="x"), output=B(value=1))]

    s = leaf.state()
    leaf.load_state(s)

    assert leaf.role == "persona"
    assert leaf.task == "v1"
    assert leaf.rules == ["r1", "r2"]
    assert len(leaf.examples) == 1
    assert leaf.examples[0].input.text == "x"
    assert leaf.examples[0].output.value == 1
    assert leaf.config.temperature == 0.0


async def test_load_state_resets_built_flag(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    await leaf.abuild()
    assert leaf._built is True

    leaf.load_state(leaf.state())

    assert leaf._built is False
    assert leaf._graph is None


def test_state_nests_children_under_attribute_names(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    s = p.state()

    assert set(s.children.keys()) == {"stage_0", "stage_1"}
    assert s.children["stage_0"].class_name == "FakeLeaf"
    assert s.children["stage_0"].input_type_name == "A"
    assert s.children["stage_1"].input_type_name == "B"


def test_load_state_recurses_into_children(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B, task="orig-0")
    leaf2 = FakeLeaf(config=cfg, input=B, output=C, task="orig-1")
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    s = p.state()
    s.children["stage_0"].task = "patched-0"
    s.children["stage_1"].rules = ["x"]
    p.load_state(s)

    assert p.stage_0.task == "patched-0"
    assert p.stage_1.rules == ["x"]


# --- load_state shape-mismatch errors ---------------------------------------


def test_load_state_extra_child_raises(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    s = leaf.state()
    s.children["bogus"] = leaf.state()

    with pytest.raises(BuildError) as ei:
        leaf.load_state(s)
    assert ei.value.reason == "prompt_incomplete"


def test_load_state_missing_child_raises(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    s = p.state()
    del s.children["stage_0"]

    with pytest.raises(BuildError) as ei:
        p.load_state(s)
    assert ei.value.reason == "prompt_incomplete"


# --- clone() ----------------------------------------------------------------


def test_clone_independence_on_simple_fields(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    leaf.rules = ["r1"]

    clone = leaf.clone()
    clone.task = "v2"
    clone.rules.append("r2")
    clone.config.temperature = 0.9

    assert leaf.task == "v1"
    assert leaf.rules == ["r1"]
    assert leaf.config.temperature == 0.0
    assert clone.config.temperature == 0.9


def test_clone_deep_copies_examples(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.examples = [Example(input=A(text="x"), output=B(value=1))]

    clone = leaf.clone()
    clone.examples.append(Example(input=A(text="y"), output=B(value=2)))
    clone.examples[0].input.text = "mutated"

    assert len(leaf.examples) == 1
    assert leaf.examples[0].input.text == "x"


def test_clone_pipeline_preserves_nested_structure(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    clone = p.clone()

    assert list(clone._children) == list(p._children)
    assert clone.stage_0 is not p.stage_0
    assert clone.stage_1 is not p.stage_1
    assert clone._stages[0] is clone.stage_0
    assert clone._stages[1] is clone.stage_1
    assert clone._stages[0] is not p._stages[0]


def test_clone_shared_child_is_deduped(cfg) -> None:
    shared = FakeLeaf(config=cfg, input=A, output=B)
    t = _TwoRefs(shared)
    assert t.first is t.second

    clone = t.clone()

    assert clone.first is clone.second
    assert clone.first is not shared


def test_clone_default_forward_leaf_drops_non_agent_extras(cfg) -> None:
    leaf = _DefaultForwardLeaf(config=cfg, input=A, output=B)
    leaf.fake_strands_state = ["heavy"]  # type: ignore[attr-defined]

    clone = leaf.clone()

    assert "fake_strands_state" not in clone.__dict__


def test_clone_composite_preserves_non_agent_extras(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 5})

    clone = leaf.clone()

    assert clone.canned == {"value": 5}
    clone.canned["value"] = 99
    assert leaf.canned == {"value": 5}


async def test_clone_rebuilds_to_equivalent_graph(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)
    await p.abuild()

    clone = p.clone()
    assert clone._built is False
    assert clone._graph is None

    await clone.abuild()

    assert clone._built is True
    orig_edges = sorted((e.callee, e.input_type, e.output_type) for e in p._graph.edges)
    clone_edges = sorted((e.callee, e.input_type, e.output_type) for e in clone._graph.edges)
    assert orig_edges == clone_edges


# --- __repr__ ---------------------------------------------------------------


def test_repr_leaf_shape(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    r = repr(leaf)
    assert "FakeLeaf(" in r
    assert "input=A" in r
    assert "output=B" in r
    assert "children=[]" in r


def test_repr_composite_lists_child_names(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)
    r = repr(p)
    assert "Pipeline(" in r
    assert "input=A" in r
    assert "output=C" in r
    assert "stage_0" in r
    assert "stage_1" in r
