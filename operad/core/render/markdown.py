"""Markdown renderer: Agent state -> Markdown system prompt.

Same sections as :mod:`operad.core.render.xml` (role, task, rules,
examples, output schema) but emitted with Markdown headings and a
table for the output schema. ``Field(description=...)`` descriptions
still surface — that is the DSPy-style per-field contract.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .xml import _type_name

if TYPE_CHECKING:
    from ..agent import Agent, Example


def _escape_pipes(s: str) -> str:
    return s.replace("|", "\\|")


def _model_values_md(model: BaseModel) -> str:
    dumped = model.model_dump(mode="json")
    lines: list[str] = []
    for name, info in type(model).model_fields.items():
        value = dumped.get(name)
        body = value if isinstance(value, str) else json.dumps(value, default=str)
        desc = f" — {info.description}" if info.description else ""
        lines.append(f"- **{name}**{desc}: {body}")
    return "\n".join(lines)


def render_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def render_input(x: BaseModel) -> str:
    return "# Input\n" + _model_values_md(x)


def render_output_schema(out_cls: type[BaseModel]) -> str:
    rows = ["| Field | Type | Description |", "| --- | --- | --- |"]
    fields = out_cls.model_fields
    if not fields:
        rows.append("| _(none)_ | | |")
    for name, info in fields.items():
        desc = _escape_pipes(info.description) if info.description else ""
        rows.append(
            f"| {_escape_pipes(name)} "
            f"| {_escape_pipes(_type_name(info.annotation))} "
            f"| {desc} |"
        )
    return "# Output schema\n" + "\n".join(rows)


def render_examples(examples: "list[Example[Any, Any]]") -> str:
    blocks: list[str] = []
    for i, ex in enumerate(examples, 1):
        blocks.append(
            f"## Example {i}\n"
            f"**Input**\n{_model_values_md(ex.input)}\n\n"
            f"**Output**\n{_model_values_md(ex.output)}"
        )
    return "\n\n".join(blocks)


def render_system(agent: "Agent[Any, Any]") -> str:
    parts: list[str] = []
    if agent.role:
        parts.append(f"# Role\n{agent.role}")
    if agent.task:
        parts.append(f"# Task\n{agent.task}")
    if agent.rules:
        parts.append("# Rules\n" + render_rules(list(agent.rules)))
    if agent.examples:
        parts.append("# Examples\n" + render_examples(list(agent.examples)))
    parts.append(render_output_schema(agent.output))  # type: ignore[arg-type]
    return "\n\n".join(parts)
