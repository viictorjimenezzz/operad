"""Tests for the XML-tagged prompt renderer.

The renderer reads directly off `Agent` state (no Prompt wrapper) and
surfaces Pydantic `Field(description=...)` from both `In` and `Out`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from operad import Agent, Example
from operad.core import render


class _Question(BaseModel):
    """A user question with optional topic hint."""

    text: str = Field(default="", description="The user's question.")
    topic: str = Field(default="", description="Optional topic hint.")


class _Answer(BaseModel):
    """A reasoned answer."""

    reasoning: str = Field(default="", description="Step-by-step deliberation.")
    answer: str = Field(default="", description="Final answer, concise.")


def _agent(**overrides) -> Agent:
    class Leaf(Agent):
        input = _Question
        output = _Answer

    return Leaf(config=None, **overrides)


def test_render_system_omits_empty_sections() -> None:
    out = render.render_system(_agent())
    assert "<role" not in out
    assert "<task" not in out
    assert "<rules" not in out
    assert "<examples" not in out
    assert "<output_schema" in out  # always included


def test_render_system_includes_section_descriptions() -> None:
    out = render.render_system(_agent(role="r", task="t", rules=["a"]))
    assert "<role" in out and 'desc="Persona' in out
    assert "<task" in out and "desc" in out
    assert "<rules" in out
    assert "- a" in out


def test_render_system_includes_output_schema_with_field_descs() -> None:
    out = render.render_system(_agent())
    assert '<output_schema desc="A reasoned answer."' in out
    assert 'name="reasoning"' in out
    assert 'desc="Step-by-step deliberation."' in out
    assert 'name="answer"' in out
    assert 'desc="Final answer, concise."' in out


def test_render_user_surfaces_in_field_descriptions() -> None:
    x = _Question(text="what is 2+2?", topic="math")
    out = render.render_input(x)
    assert 'desc="A user question with optional topic hint."' in out
    assert '<text desc="The user\'s question.">what is 2+2?</text>' in out
    assert '<topic desc="Optional topic hint.">math</topic>' in out


def test_render_user_xml_escapes_values() -> None:
    x = _Question(text="<script>alert('xss')</script>")
    out = render.render_input(x)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_examples_block_serializes_typed_pairs() -> None:
    ex = Example[_Question, _Answer](
        input=_Question(text="q1", topic="t1"),
        output=_Answer(reasoning="r", answer="a"),
    )
    out = render.render_system(_agent(examples=[ex]))
    assert "<examples" in out
    assert "<example>" in out
    assert "<text" in out and "q1" in out
    assert "<reasoning" in out and "a" in out


def test_render_system_joins_sections_with_blank_lines() -> None:
    out = render.render_system(_agent(role="r", task="t"))
    assert "</role>\n\n<task" in out
