"""Tests for the Markdown and chat-template-aware renderers.

XML remains the default and is covered by ``tests/test_rendering.py``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.core.config import IOConfig
from operad.core import render


class _Question(BaseModel):
    """A user question."""

    text: str = Field(default="", description="The user's question.")


class _Answer(BaseModel):
    """A reasoned answer."""

    reasoning: str = Field(default="", description="Step-by-step deliberation.")
    answer: str = Field(default="", description="Final answer, concise.")


def _leaf_cls() -> type[Agent]:
    class Leaf(Agent):
        input = _Question
        output = _Answer
        role = "You are a careful reasoner."
        task = "Work through the problem step-by-step."
        rules = ("Show reasoning before the final answer.",)

    return Leaf


def _cfg(renderer: str = "xml") -> Configuration:
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        io=IOConfig(renderer=renderer),  # type: ignore[arg-type]
    )


def test_markdown_render_surfaces_field_descriptions_and_rules() -> None:
    agent = _leaf_cls()(config=None)
    out = render.markdown.render_system(agent)

    assert "# Role" in out
    assert "# Task" in out
    assert "# Rules" in out
    assert "- Show reasoning before the final answer." in out
    assert "# Output schema" in out
    # every Out Field(description=...) surfaces
    assert "Step-by-step deliberation." in out
    assert "Final answer, concise." in out
    # field names are in the table
    assert "| reasoning |" in out
    assert "| answer |" in out


def test_chat_render_returns_list_with_system_message_carrying_schema() -> None:
    agent = _leaf_cls()(config=None)
    out = render.chat.render_system(agent)

    assert isinstance(out, list)
    assert len(out) >= 1
    first = out[0]
    assert first["role"] == "system"
    assert "<output_schema" in first["content"]


def test_configuration_markdown_selects_markdown_path() -> None:
    agent = _leaf_cls()(config=_cfg("markdown"))
    msg = agent.format_system_message()

    assert isinstance(msg, str)
    assert "# Role" in msg
    assert "<role" not in msg  # not the XML path


def test_classvar_override_wins_over_configuration() -> None:
    class MarkdownLeaf(_leaf_cls()):  # type: ignore[misc,valid-type]
        renderer: ClassVar[str] = "markdown"

    agent = MarkdownLeaf(config=_cfg("xml"))
    msg = agent.format_system_message()

    assert isinstance(msg, str)
    assert "# Role" in msg
    assert "<role" not in msg


def test_default_remains_xml() -> None:
    agent = _leaf_cls()(config=_cfg("xml"))
    msg = agent.format_system_message()
    assert isinstance(msg, str)
    assert "<role" in msg
