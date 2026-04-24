"""Tests for ``Configuration.structuredio``.

Covers both wire-level call shape (via :mod:`tests._spy_strands`) and
the textual-JSON parse path when ``structuredio=False``.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from operad import Configuration
from operad.core.config import IOConfig, Sampling
from operad.agents.reasoning.components.reasoner import Reasoner
from operad.utils.errors import BuildError

from ._spy_strands import StrandsSpy, install_spy


class Question(BaseModel):
    text: str = Field("", description="The question posed by the user.")


class Answer(BaseModel):
    reasoning: str = Field("", description="Chain-of-thought deliberation.")
    final: str = Field("", description="The final answer committed to.")


FIELD_DESCRIPTIONS = [
    "The question posed by the user.",
    "Chain-of-thought deliberation.",
    "The final answer committed to.",
]


async def _build(structuredio: bool) -> Reasoner:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=16),
        io=IOConfig(structuredio=structuredio),
    )
    agent = Reasoner(config=cfg, input=Question, output=Answer)
    return await agent.abuild()


@pytest.mark.asyncio
async def test_structuredio_true_passes_model_and_descriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=True)
    spy = install_spy(
        monkeypatch,
        StrandsSpy(canned_structured=Answer(reasoning="r", final="42")),
    )

    envelope = await agent(Question(text="q?"))

    assert envelope.response.final == "42"
    assert spy.last_kwargs.get("structured_output_model") is Answer
    user_msg = spy.last_args[0]
    assert isinstance(user_msg, str)
    assert "The question posed by the user." in user_msg


@pytest.mark.asyncio
async def test_structuredio_false_omits_model_keeps_descriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=False)
    canned = Answer(reasoning="r", final="42").model_dump_json()
    spy = install_spy(monkeypatch, StrandsSpy(canned_text=canned))

    envelope = await agent(Question(text="q?"))

    assert envelope.response.final == "42"
    assert "structured_output_model" not in spy.last_kwargs
    user_msg = spy.last_args[0]
    assert "The question posed by the user." in user_msg

    system_msg = agent.format_system_message()
    for desc in FIELD_DESCRIPTIONS[1:]:
        assert desc in system_msg
    assert "<output_schema" in system_msg


@pytest.mark.asyncio
async def test_structuredio_false_malformed_raises_output_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=False)
    install_spy(monkeypatch, StrandsSpy(canned_text="not json at all"))

    with pytest.raises(BuildError) as exc:
        await agent(Question(text="q?"))
    assert exc.value.reason == "output_mismatch"
