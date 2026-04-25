"""Offline tests for the new prompt-shaping knobs:

* ``Agent.stateless`` — every ``invoke()`` runs against a transient
  strands.Agent built from the leaf's resolved model and the per-call
  composed system prompt, so concurrent fan-out on a single Agent
  instance does not race on shared strands state. Subclasses opt into
  chat-style memory with ``stateless = False``, which falls back to
  mutating ``self`` (single-threaded by contract).
* ``Agent.style`` — sibling to ``role``/``task`` rendered as ``<style>``
  and exposed as a trainable ``TextParameter``.
* ``Agent.reasoning_field`` — opt-in DSPy-style ChainOfThought channel
  that augments the wire schema with a leading reasoning text field and
  strips it back out before the typed ``Out`` is returned.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.core.config import IOConfig

from .._helpers.spy_strands import StrandsSpy, install_spy


class _In(BaseModel):
    msg: str = Field(default="", description="User message.")


class _Out(BaseModel):
    reply: str = Field(default="", description="Reply text.")


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        io=IOConfig(structuredio=True),
    )


# --------------------------------------------------------------------------- #
# stateless: messages are cleared per invoke
# --------------------------------------------------------------------------- #


class _StatelessLeaf(Agent[_In, _Out]):
    input = _In
    output = _Out
    role = "r"
    task = "t"


class _StatefulLeaf(Agent[_In, _Out]):
    input = _In
    output = _Out
    role = "r"
    task = "t"
    stateless = False


@pytest.mark.asyncio
async def test_stateless_invoke_uses_transient_strands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every call goes through a transient — operad's own ``self.messages``
    and ``self.system_prompt`` are never mutated by ``forward``."""
    agent = await _StatelessLeaf(config=_cfg()).abuild()
    spy = install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    # Snapshot what build() wired into self; it must stay unchanged.
    pre_msgs = list(agent.messages)
    pre_sp = agent.system_prompt

    await agent(_In(msg="hi"))
    await agent(_In(msg="bye"))

    assert agent.messages == pre_msgs
    assert agent.system_prompt == pre_sp
    # The spy ran on the transient — and the transient was constructed
    # with the freshly composed system prompt, which (since this leaf has
    # no system-flagged input fields) equals the static base.
    assert all(sp == pre_sp for sp in spy.system_prompts)
    assert len(spy.system_prompts) == 2


@pytest.mark.asyncio
async def test_stateless_concurrent_fanout_is_reentrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reusing one stateless instance under ``asyncio.gather`` must not
    interleave per-call state across coroutines."""

    class _MixedIn(BaseModel):
        ctx: str = Field(
            default="",
            description="Per-call system context.",
            json_schema_extra={"operad": {"system": True}},
        )
        msg: str = Field(default="", description="User message.")

    class _Leaf(Agent[_MixedIn, _Out]):
        input = _MixedIn
        output = _Out
        role = "r"
        task = "t"

    agent = await _Leaf(config=_cfg()).abuild()
    spy = install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    inputs = [_MixedIn(ctx=f"ctx-{i}", msg=f"m-{i}") for i in range(5)]
    await asyncio.gather(*(agent(x) for x in inputs))

    # Every per-call ctx string appears in exactly one captured system
    # prompt — no coroutine saw another's per-call payload.
    assert len(spy.system_prompts) == 5
    for i in range(5):
        marker = f"ctx-{i}"
        hits = [sp for sp in spy.system_prompts if sp and marker in sp]
        assert len(hits) == 1, f"{marker} should appear in exactly one call"


@pytest.mark.asyncio
async def test_stateful_subclass_preserves_history_and_mutates_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``stateless=False`` opts back into chat-style behaviour: the operad
    Agent itself becomes the strands target, ``self.system_prompt`` is
    refreshed per call, and ``self.messages`` is left alone so
    conversation history accumulates across turns."""
    agent = await _StatefulLeaf(config=_cfg()).abuild()
    install_spy(monkeypatch, StrandsSpy(canned_structured=_Out(reply="ok")))

    pre = [{"role": "user", "content": [{"text": "carry over"}]}]
    agent.messages = list(pre)
    await agent(_In(msg="hi"))
    # forward() does not reset history when the subclass opts out.
    assert agent.messages == pre


# --------------------------------------------------------------------------- #
# style: rendered as a sibling section, trainable as TextParameter
# --------------------------------------------------------------------------- #


def test_style_section_omitted_when_empty() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        role = "r"
        task = "t"

    sm = _Leaf(config=None).format_system_message()
    assert isinstance(sm, str)
    assert "<style" not in sm


def test_style_section_emitted_when_set() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        role = "r"
        task = "t"

    a = _Leaf(config=None)
    a.style = "Be terse. No preamble."
    sm = a.format_system_message()
    assert isinstance(sm, str)
    assert "<style" in sm
    assert "Be terse. No preamble." in sm


def test_style_diff_localized_to_style_section() -> None:
    """Setting style mutates only the `<style>` block, leaving everything
    else byte-identical — the optimizer can move style independently."""

    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        role = "r"
        task = "t"
        rules = ("rule one",)

    a = _Leaf(config=None)
    before = a.format_system_message()
    assert isinstance(before, str)
    a.style = "Plain language."
    after = a.format_system_message()
    assert isinstance(after, str)

    # Every non-style section is preserved byte-for-byte.
    for section in ("<role", "<task", "<rules", "<output_schema"):
        # Find the section's slice in `after`; assert it appears verbatim
        # in `before` (modulo position).
        idx = after.find(section)
        assert idx != -1, f"section {section} missing after style was set"
        # Take a chunk anchored at the section header up to the next blank
        # line — enough to confirm the section's content is unchanged.
        chunk = after[idx : after.find("\n\n", idx)]
        assert chunk in before


def test_style_marked_trainable_appears_in_trainable_set() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out

    a = _Leaf(config=_cfg())
    a.mark_trainable(style=True)
    trainable = {
        path for path, p in a.named_parameters(recurse=False) if p.requires_grad
    }
    assert "style" in trainable


# --------------------------------------------------------------------------- #
# reasoning_field: schema augmentation + strip on return
# --------------------------------------------------------------------------- #


def test_effective_output_schema_is_identity_without_reasoning_field() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out

    assert _Leaf(config=None)._effective_output_schema() is _Out


def test_effective_output_schema_wraps_with_reasoning_field_first() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        reasoning_field = "thought"

    schema = _Leaf(config=None)._effective_output_schema()
    assert schema is not _Out
    fields = list(schema.model_fields.keys())
    assert fields[0] == "thought"
    assert "reply" in fields


def test_effective_output_schema_is_cached() -> None:
    """Repeat lookups return the same class so strands can key on identity."""

    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        reasoning_field = "thought"

    a = _Leaf(config=None)
    assert a._effective_output_schema() is a._effective_output_schema()


def test_reasoning_section_appears_in_rendered_output_schema() -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        role = "r"
        task = "t"
        reasoning_field = "thought"

    sm = _Leaf(config=None).format_system_message()
    assert isinstance(sm, str)
    assert 'name="thought"' in sm
    assert "Step-by-step reasoning" in sm


@pytest.mark.asyncio
async def test_reasoning_field_strips_back_to_typed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Leaf(Agent[_In, _Out]):
        input = _In
        output = _Out
        role = "r"
        task = "t"
        reasoning_field = "thought"

    agent = await _Leaf(config=_cfg()).abuild()
    wrapped = agent._effective_output_schema()
    raw = wrapped(thought="step-by-step trace", reply="final answer")
    install_spy(monkeypatch, StrandsSpy(canned_structured=raw))

    env = await agent(_In(msg="?"))
    out = env.response

    assert isinstance(out, _Out)
    assert out.reply == "final answer"
    # The typed Out has no `thought` field — the reasoning channel exists
    # only on the wire, not in the user-facing return type.
    assert "thought" not in _Out.model_fields
