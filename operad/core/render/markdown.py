"""Markdown renderer: Agent state -> Markdown system prompt.

Same sections as :mod:`operad.core.render.xml` (role, task, rules,
examples, output schema) but emitted with Markdown headings and a
table for the output schema. ``Field(description=...)`` descriptions
still surface — that is the DSPy-style per-field contract.

Runtime input is split by the ``operad.system`` marker the same way
the XML renderer does: :func:`render_input` emits user fields only,
:func:`render_system_input` emits a ``## System inputs`` block with
system-flagged fields. :func:`render_examples` keeps rendering the
complete input for both halves (demonstration, not a live call).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..fields import split_fields
from .xml import _type_name

if TYPE_CHECKING:
    from ..agent import Agent, Example


def _escape_pipes(s: str) -> str:
    return s.replace("|", "\\|")


def _field_line_md(name: str, info: Any, value: Any) -> str:
    body = value if isinstance(value, str) else json.dumps(value, default=str)
    desc = f" — {info.description}" if info.description else ""
    return f"- **{name}**{desc}: {body}"


def _model_values_md(model: BaseModel) -> str:
    dumped = model.model_dump(mode="json")
    fields = type(model).model_fields
    return "\n".join(
        _field_line_md(name, info, dumped.get(name)) for name, info in fields.items()
    )


def _model_values_md_subset(model: BaseModel, names: list[str]) -> str:
    dumped = model.model_dump(mode="json")
    fields = type(model).model_fields
    return "\n".join(
        _field_line_md(name, fields[name], dumped.get(name)) for name in names
    )


def render_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def render_input(x: BaseModel) -> str:
    """Per-call user message: user-flagged fields only."""
    _, user_names = split_fields(type(x))
    if not user_names:
        return ""
    return "# Input\n" + _model_values_md_subset(x, user_names)


def render_system_input(x: BaseModel) -> str:
    """System-flagged fields as a ``## System inputs`` block."""
    sys_names, _ = split_fields(type(x))
    if not sys_names:
        return ""
    return "## System inputs\n" + _model_values_md_subset(x, sys_names)


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
    """Render few-shot pairs with full inputs (system + user fields together)."""
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
