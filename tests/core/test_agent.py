"""Tests for `Agent`: child tracking, invoke guards, and contract checks."""

from __future__ import annotations
import pytest
from operad import Agent, BuildError
from ..conftest import A, B, C, BrokenOutputLeaf, FakeLeaf
from pydantic import ValidationError
from operad import Agent, BuildError, Configuration, Example
from ..conftest import A, B
import io
from typing import Any
from operad import Agent, AgentDiff, Configuration, Example, Pipeline
from ..conftest import A, B, C, FakeLeaf
from operad import Agent, AgentState, BuildError, Example, Pipeline


# --- from test_agent.py ---
pytestmark = pytest.mark.asyncio


async def test_assigning_agent_attribute_registers_child(cfg) -> None:
    class Composite(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.inner = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            await self.inner(x)
            return C.model_construct()

    c = Composite()
    assert "inner" in c._children
    assert c._children["inner"] is c.inner


async def test_non_agent_attributes_do_not_pollute_children(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.some_string = "hello"  # type: ignore[attr-defined]
    leaf.some_dict = {"k": 1}  # type: ignore[attr-defined]
    assert leaf._children == {}


async def test_invoke_before_build_raises_not_built(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        await leaf(A(text="hi"))
    assert exc.value.reason == "not_built"


async def test_invoke_with_wrong_input_type_raises_input_mismatch(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    with pytest.raises(BuildError) as exc:
        await leaf(B(value=1))  # wrong type: expected A
    assert exc.value.reason == "input_mismatch"


async def test_leaf_returning_wrong_type_raises_output_mismatch(cfg) -> None:
    leaf = BrokenOutputLeaf(
        config=cfg, input=A, output=B, wrong=C(label="nope")
    )
    with pytest.raises(BuildError) as exc:
        await leaf.abuild()
    assert exc.value.reason == "output_mismatch"


async def test_prompt_fields_mutable_before_build(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    leaf.task = "v2"
    leaf.config.sampling.temperature = 0.1
    await leaf.abuild()
    assert leaf.task == "v2"
    assert leaf.config.sampling.temperature == 0.1


async def test_invoke_after_build_returns_correct_type(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 42}
    ).abuild()
    out = await leaf(A(text="hi"))
    assert isinstance(out.response, B)
    assert out.response.value == 42


async def test_agent_is_built_flag_flips(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    assert leaf._built is False
    await leaf.abuild()
    assert leaf._built is True


async def test_build_from_inside_loop_raises_runtime_error(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(RuntimeError, match="running event loop"):
        leaf.build()

# --- from test_agent_init.py ---
def test_class_attrs_supply_defaults(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        role = "persona"
        task = "objective"
        rules = ("r1", "r2")

    leaf = Leaf(config=cfg)
    assert leaf.role == "persona"
    assert leaf.task == "objective"
    assert leaf.rules == ["r1", "r2"]
    assert leaf.input is A
    assert leaf.output is B
    assert leaf.config is cfg


def test_explicit_kwargs_override_class_attrs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        role = "default"
        task = "default"
        rules = ("default",)

    leaf = Leaf(
        config=cfg,
        role="custom",
        task="custom-task",
        rules=["custom-rule"],
    )
    assert leaf.role == "custom"
    assert leaf.task == "custom-task"
    assert leaf.rules == ["custom-rule"]


def test_kwarg_input_output_override_class_attrs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = A  # wrong on purpose; kwarg overrides

    leaf = Leaf(config=cfg, output=B)
    assert leaf.input is A
    assert leaf.output is B


def test_missing_input_output_raises_prompt_incomplete(cfg: Configuration) -> None:
    class Leaf(Agent):
        pass  # no input/output class attrs

    with pytest.raises(BuildError) as exc:
        Leaf(config=cfg)
    assert exc.value.reason == "prompt_incomplete"


def test_class_attrs_dont_leak_between_subclasses(cfg: Configuration) -> None:
    class LeafOne(Agent):
        input = A
        output = B
        role = "one"

    class LeafTwo(Agent):
        input = A
        output = B
        role = "two"

    assert LeafOne(config=cfg).role == "one"
    assert LeafTwo(config=cfg).role == "two"


def test_rules_tuple_is_copied_into_list(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        rules = ("r1",)

    leaf = Leaf(config=cfg)
    assert leaf.rules == ["r1"]
    leaf.rules.append("r2")  # per-instance mutation must not leak to class
    assert Leaf.rules == ("r1",)


def test_examples_accepts_typed_pairs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B

    ex = Example[A, B](input=A(text="q"), output=B(value=1))
    leaf = Leaf(config=cfg, examples=[ex])
    assert len(leaf.examples) == 1
    assert leaf.examples[0].input.text == "q"


def test_example_roundtrips_typed_pair() -> None:
    e: Example[A, B] = Example[A, B](input=A(text="hi"), output=B(value=42))
    assert isinstance(e.input, A)
    assert isinstance(e.output, B)
    assert e.model_dump() == {"input": {"text": "hi"}, "output": {"value": 42}}


def test_example_rejects_non_basemodel_values() -> None:
    with pytest.raises(ValidationError):
        Example[A, B](input=42, output=B(value=1))  # type: ignore[arg-type]


def test_missing_config_for_default_leaf_fails_build(cfg: Configuration) -> None:
    """Default-forward leaves must have a config; build catches it."""
    import asyncio

    class Leaf(Agent):
        input = A
        output = B

    async def go() -> None:
        leaf = Leaf(config=None)
        await leaf.abuild()

    with pytest.raises(BuildError) as exc:
        asyncio.run(go())
    assert exc.value.reason == "prompt_incomplete"

# --- from test_agent_introspection.py ---
class _DefaultLeaf(Agent[Any, Any]):
    """A default-forward leaf — the only kind `operad()` prints."""

    input = A
    output = B


# --- operad() / operad_dump() -----------------------------------------------


def test_operad_dump_lists_only_default_forward_leaves(cfg: Configuration) -> None:
    leaf = _DefaultLeaf(config=cfg, role="persona", task="do the thing")

    dump = leaf.operad_dump()

    assert list(dump) == ["_DefaultLeaf"]
    prompt = dump["_DefaultLeaf"]
    assert "persona" in prompt
    assert "do the thing" in prompt
    assert "<output_schema" in prompt


def test_operad_dump_skips_custom_forward_leaves(cfg: Configuration) -> None:
    fake = FakeLeaf(config=cfg, input=A, output=B, task="fake")

    dump = fake.operad_dump()

    assert dump == {}


def test_operad_dump_skips_composites_but_walks_children(cfg: Configuration) -> None:
    leaf1 = _DefaultLeaf(config=cfg, task="t1", input=A, output=B)
    leaf2 = _DefaultLeaf(config=cfg, task="t2", input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    dump = p.operad_dump()

    assert set(dump) == {"Pipeline.stage_0", "Pipeline.stage_1"}
    assert "t1" in dump["Pipeline.stage_0"]
    assert "t2" in dump["Pipeline.stage_1"]


def test_operad_prints_labelled_blocks(cfg: Configuration) -> None:
    leaf1 = _DefaultLeaf(config=cfg, task="first", input=A, output=B)
    leaf2 = _DefaultLeaf(config=cfg, task="second", input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)

    buf = io.StringIO()
    p.operad(file=buf)
    text = buf.getvalue()

    assert "=== Pipeline.stage_0 ===" in text
    assert "=== Pipeline.stage_1 ===" in text
    assert "first" in text
    assert "second" in text


def test_operad_handles_empty_tree(cfg: Configuration) -> None:
    fake = FakeLeaf(config=cfg, input=A, output=B)
    buf = io.StringIO()

    fake.operad(file=buf)

    assert "(no default-forward leaves)" in buf.getvalue()


# --- diff() ------------------------------------------------------------------


def test_diff_identical_agents_is_empty(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, task="same")
    b = a.clone()

    d = a.diff(b)

    assert isinstance(d, AgentDiff)
    assert not d
    assert len(d) == 0
    assert str(d) == "(no changes)"


def test_diff_detects_role_and_task_changes(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, task="do X")
    a.role = "persona one"
    b = a.clone()
    b.role = "persona two"
    b.task = "do Y"

    kinds = {c.kind for c in a.diff(b).changes}

    assert "role" in kinds
    assert "task" in kinds


def test_diff_detects_rules_change_with_line_diff(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B)
    a.rules = ["r1", "r2"]
    b = a.clone()
    b.rules = ["r1", "r2-edited", "r3"]

    d = a.diff(b)
    rules_changes = [c for c in d.changes if c.kind == "rules"]

    assert len(rules_changes) == 1
    detail = rules_changes[0].detail
    assert "r2" in detail
    assert "r3" in detail


def test_diff_detects_examples_add_and_remove(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B)
    a.examples = [Example(input=A(text="x"), output=B(value=1))]
    b = a.clone()
    b.examples = [Example(input=A(text="y"), output=B(value=2))]

    d = a.diff(b)
    ex_changes = [c for c in d.changes if c.kind == "examples"]

    assert len(ex_changes) == 1
    assert "'x'" in ex_changes[0].detail or "x" in ex_changes[0].detail
    assert "y" in ex_changes[0].detail


def test_diff_detects_config_field_changes(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B)
    b = a.clone()
    b.config.sampling.temperature = 0.9
    b.config.sampling.max_tokens = 512

    d = a.diff(b)
    cfg_changes = [c for c in d.changes if c.kind == "config"]

    assert len(cfg_changes) == 1
    detail = cfg_changes[0].detail
    assert "temperature" in detail
    assert "0.9" in detail
    assert "max_tokens" in detail


def test_diff_detects_added_and_removed_children(cfg: Configuration) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p1 = Pipeline(leaf1, leaf2, input=A, output=C)

    leaf1b = FakeLeaf(config=cfg, input=A, output=B)
    p2 = Pipeline(leaf1b, input=A, output=B)

    d = p1.diff(p2)
    kinds = {(c.path, c.kind) for c in d.changes}

    assert ("Pipeline.stage_1", "removed") in kinds


def test_diff_does_not_mutate_either_agent(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    b = a.clone()
    b.task = "v2"

    before_a = a.state()
    before_b = b.state()
    a.diff(b)

    assert a.state() == before_a
    assert b.state() == before_b


def test_diff_str_is_nonempty_when_changes_exist(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    b = a.clone()
    b.task = "v2"

    s = str(a.diff(b))

    assert s != "(no changes)"
    assert "task" in s


# --- _repr_html_ -------------------------------------------------------------


async def test_graph_repr_html_contains_mermaid(cfg: Configuration) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)
    await p.abuild()

    html = p._graph._repr_html_()

    assert html.startswith('<pre class="mermaid">')
    assert html.endswith("</pre>")
    assert "flowchart" in html


async def test_agent_repr_html_delegates_when_built(cfg: Configuration) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(leaf1, leaf2, input=A, output=C)
    await p.abuild()

    assert p._repr_html_() == p._graph._repr_html_()


def test_agent_repr_html_falls_back_before_build(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)

    html = leaf._repr_html_()

    assert html.startswith("<pre>")
    assert "FakeLeaf" in html


# --- no observer leakage -----------------------------------------------------


def test_introspection_does_not_emit_observer_events(cfg: Configuration) -> None:
    from operad.runtime.observers import base as _obs

    events: list[Any] = []

    class _Capture:
        async def on_event(self, event: Any) -> None:
            events.append(event)

    observer = _Capture()
    _obs.registry.register(observer)
    try:
        leaf1 = _DefaultLeaf(config=cfg, task="a", input=A, output=B)
        leaf2 = _DefaultLeaf(config=cfg, task="b", input=B, output=C)
        p = Pipeline(leaf1, leaf2, input=A, output=C)

        p.operad(file=io.StringIO())
        p.operad_dump()
        p.diff(p.clone())
        p._repr_html_()
    finally:
        _obs.registry.unregister(observer)

    assert events == []

# --- from test_agent_state.py ---
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
    assert s.config.sampling.temperature == 0.0
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
    assert leaf.config.sampling.temperature == 0.0


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
    clone.config.sampling.temperature = 0.9

    assert leaf.task == "v1"
    assert leaf.rules == ["r1"]
    assert leaf.config.sampling.temperature == 0.0
    assert clone.config.sampling.temperature == 0.9


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
