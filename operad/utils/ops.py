"""Typed, in-place delta-mutation ops for agents.

Ops are small, deterministic mutators that tweak a target agent (or a
descendant at a dotted path) in place. They power `Evolutionary` and
ad-hoc prompt tweaking. Each op is a Pydantic model so it serialises
cleanly into change-logs; `apply(agent)` mutates and returns nothing.

Choosing which op to apply — and its arguments — is the *caller's* job
(e.g. `Evolutionary._mutate`). Ops themselves are deterministic.
"""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ..core.config import Backend, Configuration
from .paths import _resolve

if TYPE_CHECKING:
    from ..core.agent import Agent, Example


@runtime_checkable
class Op(Protocol):
    """A typed, in-place mutation of an agent subtree."""

    name: str

    def apply(self, agent: "Agent[Any, Any]") -> None: ...


class _OpBase(BaseModel):
    """Shared Pydantic config for op dataclasses."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AppendRule(_OpBase):
    path: str
    rule: str
    name: str = "append_rule"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        target.rules = [*target.rules, self.rule]


class ReplaceRule(_OpBase):
    path: str
    index: int
    rule: str
    name: str = "replace_rule"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise ValueError(
                f"rule index {self.index} out of range for {len(rules)} rules"
            )
        rules[self.index] = self.rule
        target.rules = rules


class DropRule(_OpBase):
    path: str
    index: int
    name: str = "drop_rule"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise ValueError(
                f"rule index {self.index} out of range for {len(rules)} rules"
            )
        del rules[self.index]
        target.rules = rules


class EditTask(_OpBase):
    path: str
    task: str
    name: str = "edit_task"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        target.task = self.task


class TweakRole(_OpBase):
    path: str
    role: str
    name: str = "tweak_role"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        target.role = self.role


class DropExample(_OpBase):
    path: str
    index: int
    name: str = "drop_example"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        examples = list(target.examples)
        if not -len(examples) <= self.index < len(examples):
            raise ValueError(
                f"example index {self.index} out of range for "
                f"{len(examples)} examples"
            )
        del examples[self.index]
        target.examples = examples


class AppendExample(_OpBase):
    path: str
    example: Any
    name: str = "append_example"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        from ..core.agent import Example

        if not isinstance(self.example, Example):
            raise ValueError(
                f"AppendExample.example must be an Example, got "
                f"{type(self.example).__name__}"
            )
        target = _resolve(agent, self.path)
        target.examples = [*target.examples, self.example]


class SetTemperature(_OpBase):
    path: str
    temperature: float
    name: str = "set_temperature"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set temperature on composite at {self.path!r} "
                f"(no config)"
            )
        target.config = target.config.model_copy(
            update={"temperature": self.temperature}
        )


class SetModel(_OpBase):
    path: str
    model: str
    name: str = "set_model"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set model on composite at {self.path!r} (no config)"
            )
        target.config = target.config.model_copy(update={"model": self.model})


class SetBackend(_OpBase):
    path: str
    backend: Backend
    host: str | None = None
    name: str = "set_backend"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set backend on composite at {self.path!r} (no config)"
            )
        target.config = target.config.model_copy(
            update={"backend": self.backend, "host": self.host}
        )


class CompoundOp(_OpBase):
    """Apply a sequence of ops atomically (in order)."""

    ops: list[Any]
    name: str = "compound"

    def apply(self, agent: "Agent[Any, Any]") -> None:
        for op in self.ops:
            op.apply(agent)


__all__ = [
    "AppendExample",
    "AppendRule",
    "CompoundOp",
    "DropExample",
    "DropRule",
    "EditTask",
    "Op",
    "ReplaceRule",
    "SetBackend",
    "SetModel",
    "SetTemperature",
    "TweakRole",
]
