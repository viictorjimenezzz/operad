"""Prompt renderers for Agent contracts, inputs, and examples."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal
from xml.sax.saxutils import escape as _xml_text_escape
from xml.sax.saxutils import quoteattr as _xml_attr_quote

from pydantic import BaseModel
from pydantic.fields import FieldInfo

if TYPE_CHECKING:
    from .agent import Agent, Example


# ---------------------------------------------------------------------------
# System field markers.
# ---------------------------------------------------------------------------

_NAMESPACE = "operad"


def is_system_field(info: FieldInfo) -> bool:
    extra = info.json_schema_extra
    if not isinstance(extra, dict):
        return False
    bucket = extra.get(_NAMESPACE)
    if not isinstance(bucket, dict):
        return False
    return bool(bucket.get("system"))


def split_fields(model_cls: type[BaseModel]) -> tuple[list[str], list[str]]:
    sys_names: list[str] = []
    usr_names: list[str] = []
    for name, info in model_cls.model_fields.items():
        (sys_names if is_system_field(info) else usr_names).append(name)
    return sys_names, usr_names


# ---------------------------------------------------------------------------
# Shared helpers.
# ---------------------------------------------------------------------------

RenderFormat = Literal["xml", "markdown", "chat"]
RenderTarget = Literal["system", "input", "system_input", "output_schema", "rules", "examples"]


SECTION_DESCRIPTIONS: dict[str, str] = {
    "role": "Persona the agent adopts for every call.",
    "task": (
        "Objective accomplished on each invocation; the single most "
        "important instruction."
    ),
    "style": (
        "How the agent should express itself: tone, register, verbosity. "
        "Independent of the task - what to say vs. how to say it."
    ),
    "context": (
        "Runtime context supplied by the enclosing caller (e.g. an "
        "algorithm) so the agent knows the larger problem it is part of."
    ),
    "rules": "Hard constraints the agent must obey.",
    "examples": "Typed few-shot input/output demonstrations.",
    "system_input": (
        "Slow-changing input fields routed to the system prompt so the "
        "static base can be prompt-cached across calls."
    ),
}


def _type_name(ann: Any) -> str:
    if ann is None:
        return "None"
    if isinstance(ann, type):
        return ann.__name__
    return str(ann).replace("typing.", "")


def _is_model_class(value: Any) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _target_for(value: Any, target: RenderTarget | None) -> RenderTarget:
    if target is not None:
        return target
    if isinstance(value, BaseModel):
        return "input"
    if _is_model_class(value):
        return "output_schema"
    if isinstance(value, list):
        return "rules" if all(isinstance(item, str) for item in value) else "examples"
    return "system"


def _format_for(format: str) -> RenderFormat:
    if format in ("xml", "markdown", "chat"):
        return format  # type: ignore[return-value]
    return "xml"


# ---------------------------------------------------------------------------
# XML renderer.
# ---------------------------------------------------------------------------


class XMLRenderer:
    """Render Agent prompt material as XML-tagged text."""

    def render(
        self,
        value: Any,
        *,
        target: RenderTarget | None = None,
        reasoning_field: str | None = None,
    ) -> str:
        selected = _target_for(value, target)
        if selected == "system":
            return self.render_system(value)
        if selected == "input":
            return self.render_input(value)
        if selected == "system_input":
            return self.render_system_input(value)
        if selected == "output_schema":
            return self.render_output_schema(value, reasoning_field=reasoning_field)
        if selected == "rules":
            return self.render_rules(value)
        if selected == "examples":
            return self.render_examples(value)
        raise ValueError(f"unknown render target: {selected!r}")

    def render_rules(self, rules: list[str]) -> str:
        return "\n".join(f"- {_xml_text_escape(r)}" for r in rules)

    def render_input(self, x: BaseModel) -> str:
        _, user_names = split_fields(type(x))
        if not user_names:
            return ""
        cls_desc = self._desc_attr(type(x).__doc__.strip() if type(x).__doc__ else None)
        return f"<input{cls_desc}>\n{self._model_values_subset(x, user_names)}\n</input>"

    def render_system_input(self, x: BaseModel) -> str:
        sys_names, _ = split_fields(type(x))
        if not sys_names:
            return ""
        return self._section("system_input", self._model_values_subset(x, sys_names))

    def render_output_schema(
        self,
        out_cls: type[BaseModel],
        *,
        reasoning_field: str | None = None,
    ) -> str:
        fields: list[str] = []
        if reasoning_field:
            fields.append(
                f'    <field name="{_xml_text_escape(reasoning_field)}" type="str"'
                f" desc={_xml_attr_quote('Step-by-step reasoning written before the typed answer.')}/>"
            )
        for name, info in out_cls.model_fields.items():
            attrs = [
                f'name="{_xml_text_escape(name)}"',
                f'type="{_xml_text_escape(_type_name(info.annotation))}"',
            ]
            if info.description:
                attrs.append(f"desc={_xml_attr_quote(info.description)}")
            fields.append(f"    <field {' '.join(attrs)}/>")
        cls_desc = self._desc_attr(out_cls.__doc__.strip() if out_cls.__doc__ else None)
        body = "\n".join(fields) if fields else "    <!-- no fields -->"
        return f"<output_schema{cls_desc}>\n{body}\n</output_schema>"

    def render_examples(self, examples: "list[Example[Any, Any]]") -> str:
        blocks: list[str] = []
        for ex in examples:
            blocks.append(
                "  <example>\n"
                f"    <input>\n{self._model_values(ex.input)}\n    </input>\n"
                f"    <output>\n{self._model_values(ex.output)}\n    </output>\n"
                "  </example>"
            )
        return "\n".join(blocks)

    def render_system(self, agent: "Agent[Any, Any]") -> str:
        parts: list[str] = []
        if agent.role:
            parts.append(self._section("role", _xml_text_escape(agent.role)))
        if agent.task:
            parts.append(self._section("task", _xml_text_escape(agent.task)))
        if agent.style:
            parts.append(self._section("style", _xml_text_escape(agent.style)))
        if agent.context:
            parts.append(self._section("context", _xml_text_escape(agent.context)))
        if agent.rules:
            parts.append(self._section("rules", self.render_rules(list(agent.rules))))
        if agent.examples:
            parts.append(self._section("examples", self.render_examples(list(agent.examples))))
        parts.append(
            self.render_output_schema(
                agent.output,  # type: ignore[arg-type]
                reasoning_field=getattr(agent, "reasoning_field", None),
            )
        )
        return "\n\n".join(parts)

    def _desc_attr(self, description: str | None) -> str:
        if not description:
            return ""
        return f" desc={_xml_attr_quote(description)}"

    def _section(self, name: str, body: str) -> str:
        return f"<{name}{self._desc_attr(SECTION_DESCRIPTIONS.get(name))}>\n{body}\n</{name}>"

    def _field_line(self, name: str, info: Any, value: Any) -> str:
        desc = self._desc_attr(info.description)
        body = (
            _xml_text_escape(value)
            if isinstance(value, str)
            else _xml_text_escape(json.dumps(value, default=str))
        )
        return f"    <{name}{desc}>{body}</{name}>"

    def _model_values(self, model: BaseModel) -> str:
        dumped = model.model_dump(mode="json")
        fields = type(model).model_fields
        return "\n".join(
            self._field_line(name, info, dumped.get(name))
            for name, info in fields.items()
        )

    def _model_values_subset(self, model: BaseModel, names: list[str]) -> str:
        dumped = model.model_dump(mode="json")
        fields = type(model).model_fields
        return "\n".join(
            self._field_line(name, fields[name], dumped.get(name)) for name in names
        )


# ---------------------------------------------------------------------------
# Markdown renderer.
# ---------------------------------------------------------------------------


class MarkdownRenderer:
    """Render Agent prompt material as Markdown."""

    def render(
        self,
        value: Any,
        *,
        target: RenderTarget | None = None,
        reasoning_field: str | None = None,
    ) -> str:
        selected = _target_for(value, target)
        if selected == "system":
            return self.render_system(value)
        if selected == "input":
            return self.render_input(value)
        if selected == "system_input":
            return self.render_system_input(value)
        if selected == "output_schema":
            return self.render_output_schema(value, reasoning_field=reasoning_field)
        if selected == "rules":
            return self.render_rules(value)
        if selected == "examples":
            return self.render_examples(value)
        raise ValueError(f"unknown render target: {selected!r}")

    def render_rules(self, rules: list[str]) -> str:
        return "\n".join(f"- {r}" for r in rules)

    def render_input(self, x: BaseModel) -> str:
        _, user_names = split_fields(type(x))
        if not user_names:
            return ""
        return "# Input\n" + self._model_values_subset(x, user_names)

    def render_system_input(self, x: BaseModel) -> str:
        sys_names, _ = split_fields(type(x))
        if not sys_names:
            return ""
        return "## System inputs\n" + self._model_values_subset(x, sys_names)

    def render_output_schema(
        self,
        out_cls: type[BaseModel],
        *,
        reasoning_field: str | None = None,
    ) -> str:
        rows = ["| Field | Type | Description |", "| --- | --- | --- |"]
        fields = out_cls.model_fields
        if reasoning_field:
            rows.append(
                f"| {self._escape_pipes(reasoning_field)} | str "
                "| Step-by-step reasoning written before the typed answer. |"
            )
        if not fields and not reasoning_field:
            rows.append("| _(none)_ | | |")
        for name, info in fields.items():
            desc = self._escape_pipes(info.description) if info.description else ""
            rows.append(
                f"| {self._escape_pipes(name)} "
                f"| {self._escape_pipes(_type_name(info.annotation))} "
                f"| {desc} |"
            )
        return "# Output schema\n" + "\n".join(rows)

    def render_examples(self, examples: "list[Example[Any, Any]]") -> str:
        blocks: list[str] = []
        for i, ex in enumerate(examples, 1):
            blocks.append(
                f"## Example {i}\n"
                f"**Input**\n{self._model_values(ex.input)}\n\n"
                f"**Output**\n{self._model_values(ex.output)}"
            )
        return "\n\n".join(blocks)

    def render_system(self, agent: "Agent[Any, Any]") -> str:
        parts: list[str] = []
        if agent.role:
            parts.append(f"# Role\n{agent.role}")
        if agent.task:
            parts.append(f"# Task\n{agent.task}")
        if agent.style:
            parts.append(f"# Style\n{agent.style}")
        if agent.context:
            parts.append(f"# Context\n{agent.context}")
        if agent.rules:
            parts.append("# Rules\n" + self.render_rules(list(agent.rules)))
        if agent.examples:
            parts.append("# Examples\n" + self.render_examples(list(agent.examples)))
        parts.append(
            self.render_output_schema(
                agent.output,  # type: ignore[arg-type]
                reasoning_field=getattr(agent, "reasoning_field", None),
            )
        )
        return "\n\n".join(parts)

    def _escape_pipes(self, s: str) -> str:
        return s.replace("|", "\\|")

    def _field_line(self, name: str, info: Any, value: Any) -> str:
        body = value if isinstance(value, str) else json.dumps(value, default=str)
        desc = f" - {info.description}" if info.description else ""
        return f"- **{name}**{desc}: {body}"

    def _model_values(self, model: BaseModel) -> str:
        dumped = model.model_dump(mode="json")
        fields = type(model).model_fields
        return "\n".join(
            self._field_line(name, info, dumped.get(name))
            for name, info in fields.items()
        )

    def _model_values_subset(self, model: BaseModel, names: list[str]) -> str:
        dumped = model.model_dump(mode="json")
        fields = type(model).model_fields
        return "\n".join(
            self._field_line(name, fields[name], dumped.get(name)) for name in names
        )


# ---------------------------------------------------------------------------
# Chat renderer.
# ---------------------------------------------------------------------------


class ChatRenderer:
    """Render system material as chat messages and user material as XML text."""

    def __init__(self, xml: XMLRenderer | None = None) -> None:
        self._xml = xml if xml is not None else XMLRenderer()

    def render(
        self,
        value: Any,
        *,
        target: RenderTarget | None = None,
        reasoning_field: str | None = None,
    ) -> str | list[dict[str, str]]:
        selected = _target_for(value, target)
        if selected == "system":
            return [{"role": "system", "content": self._xml.render_system(value)}]
        if selected == "system_input":
            content = self._xml.render_system_input(value)
            if not content:
                return []
            return [{"role": "system", "content": content}]
        return self._xml.render(
            value,
            target=selected,
            reasoning_field=reasoning_field,
        )


# ---------------------------------------------------------------------------
# Public dispatch.
# ---------------------------------------------------------------------------


_XML = XMLRenderer()
_MARKDOWN = MarkdownRenderer()
_CHAT = ChatRenderer(_XML)


def render(
    value: Any,
    *,
    format: str = "xml",
    target: RenderTarget | None = None,
    reasoning_field: str | None = None,
) -> str | list[dict[str, str]]:
    selected = _format_for(format)
    renderer = {"xml": _XML, "markdown": _MARKDOWN, "chat": _CHAT}[selected]
    return renderer.render(
        value,
        target=target,
        reasoning_field=reasoning_field,
    )


__all__ = [
    "ChatRenderer",
    "MarkdownRenderer",
    "RenderFormat",
    "RenderTarget",
    "SECTION_DESCRIPTIONS",
    "XMLRenderer",
    "is_system_field",
    "render",
    "split_fields",
]
