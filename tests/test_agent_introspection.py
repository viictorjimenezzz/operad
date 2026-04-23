"""Tests for `Agent.operad()`, `Agent.diff()`, and `_repr_html_`.

Covers the contract described in `.conductor/feature-agent-introspection.md`:
prompt walk on default-forward leaves, structured state diff, HTML
rendering for notebooks, and the guarantee that none of these methods
mutate the agents or emit observer events.
"""

from __future__ import annotations

import io
from typing import Any

from operad import (
    Agent,
    AgentDiff,
    Configuration,
    Example,
    Pipeline,
)

from .conftest import A, B, C, FakeLeaf


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
    b.config.temperature = 0.9
    b.config.max_tokens = 512

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
