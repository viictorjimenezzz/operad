"""`Parameter` and `TextualGradient` — the data spine of `operad.optim`.

A `Parameter` is a typed handle onto a mutable field of an `Agent` —
`agent.role`, `agent.rules[2]`, `agent.config.sampling.temperature`,
etc. It carries the current value, a structured `TextualGradient`
produced by `backward()`, and optionally a `ParameterConstraint` that
downstream optimizers consult before committing an update. No
integration with `Agent` happens here; `agent.parameters()` and friends
live in slot 2-1.
"""

from __future__ import annotations

import re
import weakref
from typing import TYPE_CHECKING, Annotated, Any, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from operad.core.config import Backend, Configuration
from operad.core.agent import Example
from operad.utils.paths import resolve_parent

if TYPE_CHECKING:
    from operad.core.agent import Agent


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


ParameterKind = Literal[
    "role",
    "task",
    "style",
    "rules",
    "examples",
    "temperature",
    "top_p",
    "top_k",
    "model",
    "backend",
    "renderer",
    "rule_i",
    "example_i",
    "extra",
    "configuration",
]


class TextualGradient(BaseModel):
    """Structured critique flowing through `backward()`.

    `severity == 0.0` is the null-gradient sentinel — "no update needed".
    """

    message: str
    by_field: dict[str, str] = Field(default_factory=dict)
    severity: float = 1.0
    target_paths: list[str] = Field(default_factory=list)

    @classmethod
    def null_gradient(cls) -> TextualGradient:
        return cls(message="", severity=0.0)


class TextConstraint(BaseModel):
    kind: Literal["text"] = "text"
    max_length: int | None = None
    forbidden: list[str] = Field(default_factory=list)

    def validate(self, v: str) -> str:
        for bad in self.forbidden:
            if bad in v:
                raise ValueError(f"forbidden substring {bad!r} in value")
        if self.max_length is not None and len(v) > self.max_length:
            return v[: self.max_length]
        return v


class NumericConstraint(BaseModel):
    kind: Literal["numeric"] = "numeric"
    min: float | None = None
    max: float | None = None
    step: float | None = None

    def validate(self, v: float) -> float:
        if self.min is not None and v < self.min:
            return self.min
        if self.max is not None and v > self.max:
            return self.max
        return v


class VocabConstraint(BaseModel):
    kind: Literal["vocab"] = "vocab"
    allowed: list[str]

    def validate(self, v: str) -> str:
        if v not in self.allowed:
            raise ValueError(f"{v!r} not in vocab {self.allowed!r}")
        return v


class ListConstraint(BaseModel):
    kind: Literal["list"] = "list"
    max_count: int | None = None
    item: "ParameterConstraint | None" = None

    def validate(self, v: list[Any]) -> list[Any]:
        if self.item is not None:
            v = [self.item.validate(x) for x in v]
        if self.max_count is not None and len(v) > self.max_count:
            return v[: self.max_count]
        return v


class ConfigurationConstraint(BaseModel):
    """Per-backend legality + advisory budget envelope for `Configuration`.

    Vocab-style fields (`allowed_backends`, `allowed_models`,
    `renderer_choices`) are hard-error: a `Configuration` whose
    `backend` / `model` / `io.renderer` falls outside is rejected. Range
    fields (`temperature_range`, `top_p_range`, `max_tokens_range`)
    clamp silently. Budget knobs (`max_tokens_per_run`,
    `max_cost_per_run_usd`) are advisory metadata — `validate()` does
    not enforce them; `apply_rewrite` consults them via an optional
    cost estimator and downstream optimisers may reject post-step.
    """

    kind: Literal["configuration"] = "configuration"
    allowed_backends: list[Backend]
    allowed_models: dict[Backend, list[str]]
    renderer_choices: list[Literal["xml", "markdown", "chat"]] = Field(
        default_factory=lambda: ["xml", "markdown", "chat"]
    )
    temperature_range: tuple[float, float] = (0.0, 2.0)
    top_p_range: tuple[float, float] = (0.0, 1.0)
    max_tokens_range: tuple[int, int] | None = None
    max_tokens_per_run: int | None = None
    max_cost_per_run_usd: float | None = None

    def validate(self, v: Configuration) -> Configuration:
        if v.backend not in self.allowed_backends:
            raise ValueError(
                f"backend={v.backend!r} not in allowed_backends "
                f"{self.allowed_backends!r}"
            )
        models_for_backend = self.allowed_models.get(v.backend, [])
        if v.model not in models_for_backend:
            raise ValueError(
                f"model={v.model!r} not in allowed_models[{v.backend!r}] "
                f"{models_for_backend!r}"
            )
        if v.io.renderer not in self.renderer_choices:
            raise ValueError(
                f"io.renderer={v.io.renderer!r} not in renderer_choices "
                f"{self.renderer_choices!r}"
            )

        sampling_update: dict[str, Any] = {}
        lo, hi = self.temperature_range
        clamped_temp = min(hi, max(lo, v.sampling.temperature))
        if clamped_temp != v.sampling.temperature:
            sampling_update["temperature"] = clamped_temp
        if v.sampling.top_p is not None:
            lo_p, hi_p = self.top_p_range
            clamped_p = min(hi_p, max(lo_p, v.sampling.top_p))
            if clamped_p != v.sampling.top_p:
                sampling_update["top_p"] = clamped_p
        if self.max_tokens_range is not None:
            lo_t, hi_t = self.max_tokens_range
            clamped_t = min(hi_t, max(lo_t, v.sampling.max_tokens))
            if clamped_t != v.sampling.max_tokens:
                sampling_update["max_tokens"] = clamped_t

        if not sampling_update:
            return v
        return v.model_copy(
            update={"sampling": v.sampling.model_copy(update=sampling_update)}
        )


ParameterConstraint = Annotated[
    Union[
        TextConstraint,
        NumericConstraint,
        VocabConstraint,
        ListConstraint,
        ConfigurationConstraint,
    ],
    Field(discriminator="kind"),
]


ListConstraint.model_rebuild()


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------


_INDEX_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]$")


def _read_path(root: Any, path: str) -> Any:
    parent, last = resolve_parent(root, path)
    m = _INDEX_RE.match(last)
    if m:
        attr, idx = m.group(1), int(m.group(2))
        return getattr(parent, attr)[idx]
    return getattr(parent, last)


def _write_path(root: Any, path: str, value: Any) -> None:
    parent, last = resolve_parent(root, path)
    m = _INDEX_RE.match(last)
    if m:
        attr, idx = m.group(1), int(m.group(2))
        getattr(parent, attr)[idx] = value
        return
    setattr(parent, last, value)


# ---------------------------------------------------------------------------
# Parameter handles.
# ---------------------------------------------------------------------------


class Parameter(BaseModel, Generic[T]):
    """A handle onto a single trainable field of an `Agent`.

    `value` is a read-through cache of the live attribute at `path`;
    `read()` refreshes it, `write()` updates both sides. The back-
    reference to the owning agent is stored as a weakref so parameters
    do not pin their agents alive.
    """

    path: str
    kind: ParameterKind
    value: T
    requires_grad: bool = True
    grad: TextualGradient | None = None
    constraint: ParameterConstraint | None = None
    momentum_state: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _agent_ref: Any = PrivateAttr(default=None)

    def attach(self, agent: Agent[Any, Any]) -> None:
        self._agent_ref = weakref.ref(agent)

    @classmethod
    def from_agent(
        cls,
        agent: Agent[Any, Any],
        path: str,
        kind: ParameterKind,
        constraint: ParameterConstraint | None = None,
        requires_grad: bool = True,
    ) -> Parameter[Any]:
        value = _read_path(agent, path)
        p = cls(
            path=path,
            kind=kind,
            value=value,
            constraint=constraint,
            requires_grad=requires_grad,
        )
        p.attach(agent)
        return p

    def _agent(self) -> Agent[Any, Any]:
        ref = self._agent_ref
        if ref is None:
            raise RuntimeError(
                f"Parameter at {self.path!r} has no attached agent; "
                "call attach(agent) or construct via from_agent()"
            )
        agent = ref()
        if agent is None:
            raise RuntimeError(
                f"Parameter at {self.path!r} references a dead agent"
            )
        return agent

    def read(self) -> T:
        v = _read_path(self._agent(), self.path)
        self.value = v
        return v

    def write(self, new: T) -> None:
        _write_path(self._agent(), self.path, new)
        self.value = new

    def zero_grad(self) -> None:
        self.grad = None


class TextParameter(Parameter[str]):
    """Parameter over a string field (`role`, `task`)."""


class RuleListParameter(Parameter[list[str]]):
    """Parameter over the whole `rules` list."""


class ExampleListParameter(Parameter[list[Example[Any, Any]]]):
    """Parameter over the whole `examples` list."""


class FloatParameter(Parameter[float]):
    """Parameter over a numeric sampling knob (`temperature`, `top_p`)."""


class CategoricalParameter(Parameter[str]):
    """Parameter over a vocab-bounded string (`model`, `backend`, `renderer`)."""


class ConfigurationParameter(Parameter[Configuration]):
    """Parameter over the whole `Configuration` block.

    Yielded only when `mark_trainable(config=True)` is set; in that mode
    the leaf-level `temperature` / `top_p` / `model` / `backend` /
    `renderer` parameters are *not* yielded — the agent picks one
    decomposition per training run, and `config=True` wins over any
    leaf-level flags supplied alongside it.

    Mid-training backend swaps interact with concurrency slots
    (`operad.runtime.slots.SlotRegistry`); the registry keys per
    `(backend, host)`, so a swap allocates a fresh gate lazily on the
    next call. No explicit reset is needed.
    """


__all__ = [
    "CategoricalParameter",
    "ConfigurationConstraint",
    "ConfigurationParameter",
    "ExampleListParameter",
    "FloatParameter",
    "ListConstraint",
    "NumericConstraint",
    "Parameter",
    "ParameterConstraint",
    "ParameterKind",
    "RuleListParameter",
    "TextConstraint",
    "TextParameter",
    "TextualGradient",
    "VocabConstraint",
]
