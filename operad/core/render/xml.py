"""Rendering helpers: Agent state -> XML-tagged strings.

Pure functions; no `Agent` import cycle because we duck-type the agent.
XML with `desc="..."` attributes is the default (Anthropic-documented
format, well tolerated by llama.cpp / LM Studio / Ollama / OpenAI).

Two sources of ``desc`` attributes:

* Section descriptions (``<role desc="...">`` etc.) come from
  :data:`SECTION_DESCRIPTIONS` below — the library's own presentation
  metadata.
* User-defined ``In`` / ``Out`` ``Field(description=...)`` — surfaced
  inside ``<input>`` and ``<output_schema>`` as the DSPy-style per-field
  contract.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape as _xml_text_escape
from xml.sax.saxutils import quoteattr as _xml_attr_quote

from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import Agent, Example


SECTION_DESCRIPTIONS: dict[str, str] = {
    "role": "Persona the agent adopts for every call.",
    "task": (
        "Objective accomplished on each invocation; the single most "
        "important instruction."
    ),
    "rules": "Hard constraints the agent must obey.",
    "examples": "Typed few-shot input/output demonstrations.",
}


def _type_name(ann: Any) -> str:
    if ann is None:
        return "None"
    if isinstance(ann, type):
        return ann.__name__
    return str(ann).replace("typing.", "")


def _desc_attr(description: str | None) -> str:
    if not description:
        return ""
    return f" desc={_xml_attr_quote(description)}"


def _section(name: str, body: str) -> str:
    return f"<{name}{_desc_attr(SECTION_DESCRIPTIONS.get(name))}>\n{body}\n</{name}>"


def _model_values(model: BaseModel) -> str:
    """Emit one ``<field>`` per Pydantic field, with desc + value."""
    dumped = model.model_dump(mode="json")
    lines: list[str] = []
    for name, info in type(model).model_fields.items():
        desc = _desc_attr(info.description)
        value = dumped.get(name)
        body = (
            _xml_text_escape(value)
            if isinstance(value, str)
            else _xml_text_escape(json.dumps(value, default=str))
        )
        lines.append(f"    <{name}{desc}>{body}</{name}>")
    return "\n".join(lines)


def render_rules(rules: list[str]) -> str:
    return "\n".join(f"- {_xml_text_escape(r)}" for r in rules)


def render_input(x: BaseModel) -> str:
    """Render a runtime input: ``<input>`` with per-field descs."""
    cls = type(x)
    cls_desc = _desc_attr(cls.__doc__.strip() if cls.__doc__ else None)
    return f"<input{cls_desc}>\n{_model_values(x)}\n</input>"


def render_output_schema(out_cls: type[BaseModel]) -> str:
    """Render an ``<output_schema>`` listing expected Out fields."""
    fields: list[str] = []
    for name, info in out_cls.model_fields.items():
        attrs = [
            f'name="{_xml_text_escape(name)}"',
            f'type="{_xml_text_escape(_type_name(info.annotation))}"',
        ]
        if info.description:
            attrs.append(f"desc={_xml_attr_quote(info.description)}")
        fields.append(f"    <field {' '.join(attrs)}/>")
    cls_desc = _desc_attr(out_cls.__doc__.strip() if out_cls.__doc__ else None)
    body = "\n".join(fields) if fields else "    <!-- no fields -->"
    return f"<output_schema{cls_desc}>\n{body}\n</output_schema>"


def render_examples(examples: "list[Example[Any, Any]]") -> str:
    blocks: list[str] = []
    for ex in examples:
        blocks.append(
            "  <example>\n"
            f"    <input>\n{_model_values(ex.input)}\n    </input>\n"
            f"    <output>\n{_model_values(ex.output)}\n    </output>\n"
            "  </example>"
        )
    return "\n".join(blocks)


def render_system(agent: "Agent[Any, Any]") -> str:
    """Render the full system message from an Agent's static contract.

    Sections with empty values are omitted so short prompts stay short.
    ``<output_schema>`` is always included so the model knows what to
    produce.
    """
    parts: list[str] = []
    if agent.role:
        parts.append(_section("role", _xml_text_escape(agent.role)))
    if agent.task:
        parts.append(_section("task", _xml_text_escape(agent.task)))
    if agent.rules:
        parts.append(_section("rules", render_rules(list(agent.rules))))
    if agent.examples:
        parts.append(_section("examples", render_examples(list(agent.examples))))
    parts.append(render_output_schema(agent.output))  # type: ignore[arg-type]
    return "\n\n".join(parts)
