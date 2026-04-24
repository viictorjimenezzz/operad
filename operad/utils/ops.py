"""Typed, in-place delta-mutation ops for agents.

Ops are small, deterministic mutators that tweak a target agent (or a
descendant at a dotted path) in place. They power `Evolutionary` and
ad-hoc prompt tweaking. Each op is a Pydantic model so it serialises
cleanly into change-logs; `apply(agent)` mutates and returns nothing.
`undo(agent)` restores the snapshot taken at `apply`-time so mutations
are reversible when a later step fails.

Choosing which op to apply — and its arguments — is the *caller's* job
(e.g. `Evolutionary._attempt_mutate_and_build`). Ops themselves are
deterministic.
"""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

from pydantic import BaseModel, ConfigDict, PrivateAttr

from ..core.config import Backend, Configuration
from .paths import _resolve

if TYPE_CHECKING:
    from ..core.agent import Agent, Example


_UNDO_BEFORE_APPLY = "undo() called before apply()"


@runtime_checkable
class Op(Protocol):
    """A typed, in-place mutation of an agent subtree.

    Every op must support `apply`/`undo`: `apply` mutates the target
    subtree and records whatever state is needed to reverse the change;
    `undo` restores that snapshot. Calling `undo` before `apply` raises
    `RuntimeError`.
    """

    name: str

    def apply(self, agent: "Agent[Any, Any]") -> None: ...

    def undo(self, agent: "Agent[Any, Any]") -> None: ...


class _OpBase(BaseModel):
    """Shared Pydantic config for op dataclasses."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AppendRule(_OpBase):
    path: str
    rule: str
    name: str = "append_rule"

    _prev_rules: list[str] | None = PrivateAttr(default=None)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        self._prev_rules = list(target.rules)
        target.rules = [*target.rules, self.rule]

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._prev_rules is None:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.rules = self._prev_rules
        self._prev_rules = None


class ReplaceRule(_OpBase):
    path: str
    index: int
    rule: str
    name: str = "replace_rule"

    _prev_rules: list[str] | None = PrivateAttr(default=None)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise ValueError(
                f"rule index {self.index} out of range for {len(rules)} rules"
            )
        self._prev_rules = list(target.rules)
        rules[self.index] = self.rule
        target.rules = rules

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._prev_rules is None:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.rules = self._prev_rules
        self._prev_rules = None


class DropRule(_OpBase):
    path: str
    index: int
    name: str = "drop_rule"

    _prev_rules: list[str] | None = PrivateAttr(default=None)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        rules = list(target.rules)
        if not -len(rules) <= self.index < len(rules):
            raise ValueError(
                f"rule index {self.index} out of range for {len(rules)} rules"
            )
        self._prev_rules = list(target.rules)
        del rules[self.index]
        target.rules = rules

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._prev_rules is None:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.rules = self._prev_rules
        self._prev_rules = None


class EditTask(_OpBase):
    path: str
    task: str
    name: str = "edit_task"

    _prev_task: str | None = PrivateAttr(default=None)
    _applied: bool = PrivateAttr(default=False)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        self._prev_task = target.task
        self._applied = True
        target.task = self.task

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if not self._applied:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.task = self._prev_task  # type: ignore[assignment]
        self._prev_task = None
        self._applied = False


class TweakRole(_OpBase):
    path: str
    role: str
    name: str = "tweak_role"

    _prev_role: str | None = PrivateAttr(default=None)
    _applied: bool = PrivateAttr(default=False)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        self._prev_role = target.role
        self._applied = True
        target.role = self.role

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if not self._applied:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.role = self._prev_role  # type: ignore[assignment]
        self._prev_role = None
        self._applied = False


class DropExample(_OpBase):
    path: str
    index: int
    name: str = "drop_example"

    _prev_examples: list[Any] | None = PrivateAttr(default=None)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        examples = list(target.examples)
        if not -len(examples) <= self.index < len(examples):
            raise ValueError(
                f"example index {self.index} out of range for "
                f"{len(examples)} examples"
            )
        self._prev_examples = list(target.examples)
        del examples[self.index]
        target.examples = examples

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._prev_examples is None:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.examples = self._prev_examples
        self._prev_examples = None


class AppendExample(_OpBase):
    path: str
    example: Any
    name: str = "append_example"

    _prev_examples: list[Any] | None = PrivateAttr(default=None)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        from ..core.example import Example

        if not isinstance(self.example, Example):
            raise ValueError(
                f"AppendExample.example must be an Example, got "
                f"{type(self.example).__name__}"
            )
        target = _resolve(agent, self.path)
        self._prev_examples = list(target.examples)
        target.examples = [*target.examples, self.example]

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._prev_examples is None:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.examples = self._prev_examples
        self._prev_examples = None


class SetTemperature(_OpBase):
    path: str
    temperature: float
    name: str = "set_temperature"

    _prev_config: Configuration | None = PrivateAttr(default=None)
    _applied: bool = PrivateAttr(default=False)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set temperature on composite at {self.path!r} "
                f"(no config)"
            )
        self._prev_config = target.config.model_copy(deep=True)
        self._applied = True
        target.config = target.config.model_copy(
            update={
                "sampling": target.config.sampling.model_copy(
                    update={"temperature": self.temperature}
                )
            }
        )

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if not self._applied:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.config = self._prev_config
        self._prev_config = None
        self._applied = False


class SetModel(_OpBase):
    path: str
    model: str
    name: str = "set_model"

    _prev_config: Configuration | None = PrivateAttr(default=None)
    _applied: bool = PrivateAttr(default=False)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set model on composite at {self.path!r} (no config)"
            )
        self._prev_config = target.config.model_copy(deep=True)
        self._applied = True
        target.config = target.config.model_copy(update={"model": self.model})

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if not self._applied:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.config = self._prev_config
        self._prev_config = None
        self._applied = False


class SetBackend(_OpBase):
    path: str
    backend: Backend
    host: str | None = None
    name: str = "set_backend"

    _prev_config: Configuration | None = PrivateAttr(default=None)
    _applied: bool = PrivateAttr(default=False)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(
                f"cannot set backend on composite at {self.path!r} (no config)"
            )
        self._prev_config = target.config.model_copy(deep=True)
        self._applied = True
        target.config = target.config.model_copy(
            update={"backend": self.backend, "host": self.host}
        )

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if not self._applied:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        target = _resolve(agent, self.path)
        target.config = self._prev_config
        self._prev_config = None
        self._applied = False


class CompoundOp(_OpBase):
    """Apply a sequence of ops atomically (in order).

    `undo` reverses the applied children in reverse order so the overall
    mutation is fully rolled back. If `apply` fails partway through, any
    children already applied are undone before the exception propagates.
    """

    ops: list[Any]
    name: str = "compound"

    _applied_count: int = PrivateAttr(default=0)

    def apply(self, agent: "Agent[Any, Any]") -> None:
        self._applied_count = 0
        for op in self.ops:
            try:
                op.apply(agent)
            except Exception:
                for prior in reversed(self.ops[: self._applied_count]):
                    prior.undo(agent)
                self._applied_count = 0
                raise
            self._applied_count += 1

    def undo(self, agent: "Agent[Any, Any]") -> None:
        if self._applied_count == 0:
            raise RuntimeError(_UNDO_BEFORE_APPLY)
        for op in reversed(self.ops[: self._applied_count]):
            op.undo(agent)
        self._applied_count = 0


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
