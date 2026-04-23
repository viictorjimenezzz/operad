"""Typed, in-place mutation Ops for an Agent subtree.

Each Op is a small Pydantic model carrying a dotted ``path`` (resolved
via :func:`operad.utils.paths.resolve`) plus whatever parameters the
mutation needs. ``apply(agent)`` mutates the named node in place and
returns ``None``. Ops are deterministic — choosing *which* Op to apply
and *what* arguments to give it is the caller's job (e.g.
``Evolutionary``, ``Sweep``).

Invariants:

- Ops never change ``input`` / ``output`` types. Those are structural.
- ``SetTemperature`` / ``SetModel`` / ``SetBackend`` raise ``ValueError``
  when the target node has ``config is None`` (i.e. a composite).
- ``AppendRule`` is not a set operation: appending the same rule twice
  adds two copies. This matches the natural semantics of ``list.append``.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ..core.agent import Agent, Example
from ..core.config import Backend, Configuration
from .paths import resolve


@runtime_checkable
class Op(Protocol):
    """An in-place, typed mutation of a node in an Agent subtree."""

    name: ClassVar[str]

    def apply(self, agent: Agent[Any, Any]) -> None: ...


class _OpBase(BaseModel):
    """Pydantic base shared by concrete Ops.

    ``arbitrary_types_allowed`` lets Ops carry ``Example[Any, Any]``
    and other non-JSON-primitive values as fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


def _require_config(target: Agent[Any, Any], path: str, op: str) -> Configuration:
    if target.config is None:
        raise ValueError(
            f"{op} requires a leaf with a Configuration; "
            f"node at path {path!r} has config=None (composite)"
        )
    return target.config


# --- rules ------------------------------------------------------------------


class AppendRule(_OpBase):
    name: ClassVar[str] = "append_rule"
    path: str
    rule: str

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        target.rules = [*target.rules, self.rule]


class ReplaceRule(_OpBase):
    name: ClassVar[str] = "replace_rule"
    path: str
    index: int
    rule: str

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise IndexError(
                f"replace_rule index {self.index} out of range "
                f"for {len(rules)} rules at path {self.path!r}"
            )
        rules[self.index] = self.rule
        target.rules = rules


class DropRule(_OpBase):
    name: ClassVar[str] = "drop_rule"
    path: str
    index: int

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise IndexError(
                f"drop_rule index {self.index} out of range "
                f"for {len(rules)} rules at path {self.path!r}"
            )
        del rules[self.index]
        target.rules = rules


# --- task / role ------------------------------------------------------------


class EditTask(_OpBase):
    name: ClassVar[str] = "edit_task"
    path: str
    task: str

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        target.task = self.task


class TweakRole(_OpBase):
    name: ClassVar[str] = "tweak_role"
    path: str
    role: str

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        target.role = self.role


# --- examples ---------------------------------------------------------------


class AppendExample(_OpBase):
    name: ClassVar[str] = "append_example"
    path: str
    example: Example[Any, Any]

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        target.examples = [*target.examples, self.example]


class DropExample(_OpBase):
    name: ClassVar[str] = "drop_example"
    path: str
    index: int

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        examples = list(target.examples)
        if not -len(examples) <= self.index < len(examples):
            raise IndexError(
                f"drop_example index {self.index} out of range "
                f"for {len(examples)} examples at path {self.path!r}"
            )
        del examples[self.index]
        target.examples = examples


# --- config -----------------------------------------------------------------


def _reconfigure(config: Configuration, **updates: Any) -> Configuration:
    """Rebuild a Configuration so its @model_validator re-fires."""
    data = {**config.model_dump(), **updates}
    return Configuration(**data)


class SetTemperature(_OpBase):
    name: ClassVar[str] = "set_temperature"
    path: str
    temperature: float

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        cfg = _require_config(target, self.path, "set_temperature")
        target.config = _reconfigure(cfg, temperature=self.temperature)


class SetModel(_OpBase):
    name: ClassVar[str] = "set_model"
    path: str
    model: str

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        cfg = _require_config(target, self.path, "set_model")
        target.config = _reconfigure(cfg, model=self.model)


class SetBackend(_OpBase):
    name: ClassVar[str] = "set_backend"
    path: str
    backend: Backend
    host: str | None = None

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = resolve(agent, self.path)
        cfg = _require_config(target, self.path, "set_backend")
        target.config = _reconfigure(cfg, backend=self.backend, host=self.host)


# --- composition ------------------------------------------------------------


class CompoundOp(_OpBase):
    """Apply a sequence of Ops in declared order. Not atomic."""

    name: ClassVar[str] = "compound"
    ops: list[Op]

    def apply(self, agent: Agent[Any, Any]) -> None:
        for op in self.ops:
            op.apply(agent)
