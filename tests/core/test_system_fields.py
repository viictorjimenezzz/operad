"""Tests for the ``operad.system`` field marker and per-call system composition.

Covers:

* :mod:`operad.core.render` detection helpers.
* Renderer split: ``render_input`` emits user fields only,
  ``render_system_input`` emits system-flagged fields only, examples
  stay whole.
* :meth:`Agent.format_system_input` and
  :meth:`Agent._compose_system_for_call` semantics (back-compat +
  composition).
* Per-call mutation of ``self.system_prompt`` in ``forward`` so the
  static prefix stays cache-stable.
* ``OperadOutput.hash_prompt`` differentiates when system-flagged
  fields change.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from operad import Agent, Configuration, Example
from operad.core import render
from operad.core.config import IOConfig
from operad.core.render import is_system_field, split_fields

from .._helpers.spy_strands import StrandsSpy, install_spy


# --------------------------------------------------------------------------- #
# Fixtures / shared models
# --------------------------------------------------------------------------- #


def _system_field(description: str, **kwargs: Any) -> Any:
    """Test helper: build a Field carrying the operad.system marker."""
    return Field(
        default="",
        description=description,
        json_schema_extra={"operad": {"system": True}},
        **kwargs,
    )


class _MixedInput(BaseModel):
    """An input with both system- and user-flagged fields."""

    context: str = _system_field("Slow-changing persona.")
    workspace_guide: str = _system_field("Slow-changing KB guide.")
    message: str = Field(default="", description="Per-turn user message.")
    extra: str = Field(default="", description="Another per-turn field.")


class _AllUserInput(BaseModel):
    """Nothing tagged — full back-compat path."""

    message: str = Field(default="", description="User message.")


class _Out(BaseModel):
    reply: str = Field(default="", description="Reply text.")


# --------------------------------------------------------------------------- #
# Marker-detection helpers
# --------------------------------------------------------------------------- #


def test_is_system_field_detects_operad_marker() -> None:
    field = _system_field("x")
    assert is_system_field(field) is True


def test_is_system_field_rejects_plain_field() -> None:
    field = Field(default="", description="plain")
    assert is_system_field(field) is False


def test_is_system_field_rejects_unrelated_extra() -> None:
    field = Field(
        default="",
        description="x",
        json_schema_extra={"tag": "whatever"},
    )
    assert is_system_field(field) is False


def test_is_system_field_rejects_callable_extra() -> None:
    def _callable(_: Any) -> None: ...

    field = Field(default="", description="x", json_schema_extra=_callable)
    assert is_system_field(field) is False


def test_split_fields_preserves_declaration_order() -> None:
    sys_names, usr_names = split_fields(_MixedInput)
    assert sys_names == ["context", "workspace_guide"]
    assert usr_names == ["message", "extra"]


def test_split_fields_untagged_all_user() -> None:
    sys_names, usr_names = split_fields(_AllUserInput)
    assert sys_names == []
    assert usr_names == ["message"]


# --------------------------------------------------------------------------- #
# Renderer split
# --------------------------------------------------------------------------- #


def test_render_input_emits_user_fields_only() -> None:
    x = _MixedInput(
        context="persona A",
        workspace_guide="KB X",
        message="hi",
        extra="e1",
    )
    out = render.render(x)
    assert "<input" in out
    assert "<message" in out and "hi" in out
    assert "<extra" in out and "e1" in out
    # system-flagged fields must be absent
    assert "<context" not in out
    assert "<workspace_guide" not in out


def test_render_system_input_emits_system_fields_only() -> None:
    x = _MixedInput(
        context="persona A",
        workspace_guide="KB X",
        message="hi",
        extra="e1",
    )
    out = render.render(x, target="system_input")
    assert "<system_input" in out
    assert "<context" in out and "persona A" in out
    assert "<workspace_guide" in out and "KB X" in out
    # user fields must be absent
    assert "<message" not in out
    assert "<extra" not in out


def test_render_system_input_empty_when_no_system_fields() -> None:
    x = _AllUserInput(message="hi")
    assert render.render(x, target="system_input") == ""


def test_render_input_empty_when_all_fields_system() -> None:
    class _AllSystem(BaseModel):
        a: str = _system_field("a")
        b: str = _system_field("b")

    assert render.render(_AllSystem(a="x", b="y")) == ""


def test_render_examples_includes_all_fields() -> None:
    """Examples are complete demonstrations — system fields must appear."""

    class _Leaf(Agent[_MixedInput, _Out]):
        input = _MixedInput
        output = _Out

    ex = Example[_MixedInput, _Out](
        input=_MixedInput(
            context="persona A",
            workspace_guide="KB X",
            message="hi",
            extra="e1",
        ),
        output=_Out(reply="hello"),
    )
    agent = _Leaf(config=None, examples=[ex])
    system_msg = agent.format_system_message()
    assert isinstance(system_msg, str)
    # Every field surfaces inside the <examples> block
    assert "persona A" in system_msg
    assert "KB X" in system_msg
    assert "hi" in system_msg
    assert "e1" in system_msg


# --------------------------------------------------------------------------- #
# Composition semantics
# --------------------------------------------------------------------------- #


def test_compose_returns_base_verbatim_when_no_system_fields() -> None:
    """Back-compat: an input with no system markers yields identical bytes."""

    class _Leaf(Agent[_AllUserInput, _Out]):
        input = _AllUserInput
        output = _Out
        role = "r"
        task = "t"

    agent = _Leaf(config=None)
    base = agent.format_system_message()
    composed = agent._compose_system_for_call(_AllUserInput(message="hi"))
    assert composed == base


def test_compose_appends_system_input_with_fixed_separator() -> None:
    class _Leaf(Agent[_MixedInput, _Out]):
        input = _MixedInput
        output = _Out
        role = "r"
        task = "t"

    agent = _Leaf(config=None)
    base = agent.format_system_message()
    x = _MixedInput(
        context="persona A",
        workspace_guide="KB X",
        message="hi",
    )
    composed = agent._compose_system_for_call(x)

    assert composed.startswith(base)
    tail = composed[len(base):]
    assert tail.startswith("\n\n")
    # system_input block follows, with field values
    assert "<system_input" in tail
    assert "persona A" in tail
    assert "KB X" in tail
    # user fields never leak into the system side
    assert "<message" not in tail


def test_compose_prefix_is_stable_across_calls() -> None:
    """Prompt-cache prerequisite: base prefix byte-identical between calls."""

    class _Leaf(Agent[_MixedInput, _Out]):
        input = _MixedInput
        output = _Out
        role = "r"
        task = "t"

    agent = _Leaf(config=None)
    base = agent.format_system_message()

    x1 = _MixedInput(context="same", workspace_guide="same", message="hi")
    x2 = _MixedInput(context="same", workspace_guide="same", message="bye")

    composed1 = agent._compose_system_for_call(x1)
    composed2 = agent._compose_system_for_call(x2)

    # Base stays identical even though user message differs.
    assert composed1[: len(base)] == base
    assert composed2[: len(base)] == base
    # And since system fields were identical, the whole composed system is too.
    assert composed1 == composed2


def test_compose_changes_when_system_field_changes() -> None:
    class _Leaf(Agent[_MixedInput, _Out]):
        input = _MixedInput
        output = _Out
        role = "r"
        task = "t"

    agent = _Leaf(config=None)
    base = agent.format_system_message()

    x1 = _MixedInput(context="persona A", workspace_guide="KB X", message="hi")
    x2 = _MixedInput(context="persona B", workspace_guide="KB X", message="hi")

    c1 = agent._compose_system_for_call(x1)
    c2 = agent._compose_system_for_call(x2)

    assert c1 != c2
    # But the base stays identical — cache key prefix.
    assert c1.startswith(base)
    assert c2.startswith(base)


# --------------------------------------------------------------------------- #
# forward mutates self.system_prompt before the strands call
# --------------------------------------------------------------------------- #


class _SpyLeaf(Agent[_MixedInput, _Out]):
    input = _MixedInput
    output = _Out
    role = "r"
    task = "t"


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        io=IOConfig(structuredio=True),
    )


@pytest.mark.asyncio
async def test_per_call_system_prompt_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _SpyLeaf(config=_cfg()).abuild()
    spy = install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    x1 = _MixedInput(context="persona A", workspace_guide="KB X", message="hi")
    x2 = _MixedInput(context="persona B", workspace_guide="KB Y", message="bye")
    await agent(x1)
    await agent(x2)

    sp1, sp2 = spy.system_prompts
    assert sp1 is not None and sp2 is not None
    assert "persona A" in sp1
    assert "KB X" in sp1
    assert "persona B" in sp2
    assert "KB Y" in sp2
    # user-side fields must stay out of the system prompt.
    assert "hi" not in sp1
    assert "bye" not in sp2


@pytest.mark.asyncio
async def test_system_prompt_stable_when_system_fields_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _SpyLeaf(config=_cfg()).abuild()
    spy = install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    x1 = _MixedInput(context="same", workspace_guide="same", message="first")
    x2 = _MixedInput(context="same", workspace_guide="same", message="second")
    await agent(x1)
    await agent(x2)

    sp1, sp2 = spy.system_prompts
    assert sp1 == sp2  # byte-for-byte identical → cache hit


# --------------------------------------------------------------------------- #
# hash_prompt differentiates on system-field changes
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_hash_prompt_differentiates_on_system_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _SpyLeaf(config=_cfg()).abuild()
    install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    x_same_sys_a = _MixedInput(
        context="persona A", workspace_guide="KB X", message="hi"
    )
    x_same_sys_b = _MixedInput(
        context="persona A", workspace_guide="KB X", message="bye"
    )
    x_new_sys = _MixedInput(
        context="persona B", workspace_guide="KB X", message="hi"
    )

    env_a = await agent(x_same_sys_a)
    env_b = await agent(x_same_sys_b)
    env_c = await agent(x_new_sys)

    # User-only change still changes the hash (user message differs).
    assert env_a.hash_prompt != env_b.hash_prompt
    # System-field change also changes the hash.
    assert env_a.hash_prompt != env_c.hash_prompt
