"""The `Agent` base class.

A `operad.Agent` is a typed, composable component with PyTorch-style
child tracking and a `build()` step. The Strands runtime is wrapped
internally by `operad.core._strands_runner.StrandsRunner` for default-
forward leaves; nothing else in operad imports `strands.Agent`.
Everything a user would have put on a separate `Prompt` object — role,
task, rules, examples, typed input/output, config — lives directly on
the Agent. Class-level attribute defaults play the role of module
hyperparameters; instance attributes carry the live values, freely
mutable before `build()`.
"""

from __future__ import annotations

import asyncio
import copy
import html as _html
import inspect
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, Literal, Self, TextIO, TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model

from ._strands_runner import StrandsRunner

from ..runtime import acquire as _acquire_slot
from ..runtime.retry import with_retry as _with_retry
from ..runtime.streaming import ChunkEvent
from ..utils.errors import BuildError
from .config import Configuration
from .diff import AgentDiff, diff_states
from .example import Example
from .output import (
    OPERAD_VERSION_HASH,
    PYTHON_VERSION_HASH,
    OperadOutput,
    _RUN_GRAPH_HASH,
)
from ..utils.hashing import (
    hash_config,
    hash_json,
    hash_schema,
    hash_str,
)
from .state import AgentState
from . import render
from .gradmode import _inference_mode_active

if TYPE_CHECKING:
    from .build import Tracer
    from ..optim.parameter import Parameter


In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


def _system_to_str(rendered: str | list[dict[str, str]] | None) -> str:
    if rendered is None:
        return ""
    if isinstance(rendered, list):
        return "\n\n".join(
            m.get("content", "") for m in rendered if m.get("role") == "system"
        )
    return rendered


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, BaseModel):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return repr(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _json_safe(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


# Per-task tracer. When set, `Agent.invoke` short-circuits into the tracer
# instead of validating and running `forward`. This is how `build()` performs
# symbolic tracing without touching an LLM.
_TRACER: ContextVar["Tracer | None"] = ContextVar("_TRACER", default=None)


_LOCAL_FIELD_TO_PATH: dict[str, str] = {
    "role": "role",
    "task": "task",
    "style": "style",
    "rules": "rules",
    "examples": "examples",
    "temperature": "config.sampling.temperature",
    "top_p": "config.sampling.top_p",
    "config": "config",
}


class Handle:
    """Return value of ``Agent.register_*_hook``; call ``remove()`` to unregister.

    Idempotent: a second ``remove()`` is a no-op, as is removal after the
    underlying callback list has already been cleared (e.g. by ``clone()``).
    """

    def __init__(self, bucket: list[Callable[..., Any]], fn: Callable[..., Any]) -> None:
        self._bucket = bucket
        self._fn = fn
        self._removed = False

    def remove(self) -> None:
        if self._removed:
            return
        try:
            self._bucket.remove(self._fn)
        except ValueError:
            pass
        self._removed = True


_REASONING_FIELD_DESC = (
    "Step-by-step reasoning written before the typed answer."
)
_REASONING_WRAPPER_CACHE: dict[tuple[type[BaseModel], str], type[BaseModel]] = {}


def _wrap_with_reasoning(
    out_cls: type[BaseModel], field_name: str
) -> type[BaseModel]:
    """Build a Pydantic subclass with `field_name` declared first.

    Cached per `(out_cls, field_name)` so repeat calls return the same
    class — strands and any downstream caching key on identity.
    """
    key = (out_cls, field_name)
    cached = _REASONING_WRAPPER_CACHE.get(key)
    if cached is not None:
        return cached
    fields: dict[str, Any] = {
        field_name: (
            str,
            Field(default="", description=_REASONING_FIELD_DESC),
        ),
    }
    for name, info in out_cls.model_fields.items():
        fields[name] = (info.annotation, info)
    wrapped = create_model(  # type: ignore[call-overload]
        f"{out_cls.__name__}WithReasoning",
        **fields,
    )
    _REASONING_WRAPPER_CACHE[key] = wrapped
    return wrapped


def _strip_reasoning(
    raw: BaseModel, out_cls: type[BaseModel], field_name: str
) -> BaseModel:
    """Drop the reasoning field from a wrapped instance and revalidate."""
    data = raw.model_dump()
    data.pop(field_name, None)
    return out_cls.model_validate(data)


def _extract_text(result: Any) -> str:
    """Join every text content block from a strands ``AgentResult``."""
    message = getattr(result, "message", None)
    if message is None:
        return ""
    content = message.get("content", []) if isinstance(message, dict) else getattr(
        message, "content", []
    )
    return "".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    )


def _extract_tokens(result: Any) -> int:
    """Best-effort total tokens from a strands result; 0 if unknown.

    The strands result shape isn't contracted in-repo; feed whatever
    integer fields it exposes into the slot's TPM settle without
    guessing a schema we don't own.
    """
    if result is None:
        return 0
    try:
        p = int(getattr(result, "prompt_tokens", 0) or 0)
        c = int(getattr(result, "completion_tokens", 0) or 0)
    except (TypeError, ValueError):
        return 0
    return p + c


class Agent(Generic[In, Out]):
    """Typed, composable agent.

    Subclass this to define either a leaf (use the default ``forward``,
    which delegates to a wrapped ``strands.Agent`` via
    :class:`StrandsRunner` with structured output) or a composite
    (override ``forward`` to route between sub-agents, which are
    auto-registered when assigned as attributes).

    Component subclasses declare their contract at the class level::

        class Reasoner(Agent[Question, Answer]):
            input = Question
            output = Answer
            role = "You are a careful reasoner."
            task = "Work through the problem step by step."
            rules = ("Show reasoning before the answer.",)

    Instantiate as ``Reasoner(config=cfg)``; any constructor kwarg
    overrides the matching class attribute.

    The Strands runner is constructed at ``build()`` time so that
    constructing an Agent never touches a provider and every attribute
    stays mutable beforehand.
    """

    # --- class-level defaults (override in subclasses) ----------------------
    input: ClassVar[type[BaseModel] | None] = None
    output: ClassVar[type[BaseModel] | None] = None
    role: ClassVar[str] = ""
    task: ClassVar[str] = ""
    style: ClassVar[str] = ""
    context: ClassVar[str] = ""
    name: ClassVar[str] = ""
    rules: ClassVar[Sequence[str]] = ()
    examples: ClassVar[Sequence[Example[Any, Any]]] = ()
    renderer: ClassVar[str | None] = None
    default_sampling: ClassVar[dict[str, Any]] = {}
    # Each invoke() depends only on the freshly-composed system + user
    # message; strands' per-instance `messages` log is cleared before
    # every call so iterative algorithms can reuse one Agent without
    # earlier turns leaking into later ones. Subclasses that genuinely
    # want chat-style memory (e.g. multi-turn dialogue) override to False.
    stateless: ClassVar[bool] = True
    # Opt-in DSPy-style ChainOfThought: when set, the effective output
    # schema sent to strands is augmented with a leading text field of
    # this name so the model commits its reasoning before the typed
    # answer. Structural — not part of the trainable surface.
    reasoning_field: ClassVar[str | None] = None

    # --- instance state (populated by __init__ / build) ---------------------
    config: Configuration | None
    name: str
    _built: bool
    _children: dict[str, "Agent[Any, Any]"]
    _graph: Any  # populated by build(); typed as AgentGraph in operad.core.build

    def __init__(
        self,
        *,
        config: Configuration | None = None,
        role: str | None = None,
        task: str | None = None,
        style: str | None = None,
        context: str | None = None,
        name: str | None = None,
        rules: Sequence[str] | None = None,
        examples: Sequence[Example[In, Out]] | None = None,
        input: type[In] | None = None,
        output: type[Out] | None = None,
    ) -> None:
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_built", False)
        object.__setattr__(self, "_graph", None)
        object.__setattr__(self, "_runner", None)
        object.__setattr__(self, "_requires_grad_overrides", {})
        object.__setattr__(self, "_configuration_constraint", None)
        object.__setattr__(self, "_forward_pre_hooks", [])
        object.__setattr__(self, "_forward_hooks", [])
        object.__setattr__(self, "_backward_hooks", [])

        cls = type(self)
        in_cls = input if input is not None else cls.input
        out_cls = output if output is not None else cls.output
        if in_cls is None or out_cls is None:
            raise BuildError(
                "prompt_incomplete",
                f"{cls.__name__} has no input/output type; set them as "
                f"class attributes or pass `input=`/`output=`",
                agent=cls.__name__,
            )

        self.config = config
        self.role = role if role is not None else cls.role
        self.task = task if task is not None else cls.task
        self.style = style if style is not None else cls.style
        self.context = context if context is not None else cls.context
        self.name = name if name is not None else (cls.name or cls.__name__)
        self.rules = list(rules if rules is not None else cls.rules)
        self.examples = list(examples if examples is not None else cls.examples)
        self.input = in_cls
        self.output = out_cls

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Agent):
            children = self.__dict__.get("_children")
            if children is None:
                object.__setattr__(self, "_children", {})
                children = self.__dict__["_children"]
            children[name] = value
        object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        in_name = self.input.__name__ if self.input is not None else "?"
        out_name = self.output.__name__ if self.output is not None else "?"
        return (
            f"{type(self).__name__}("
            f"name={self.name}, "
            f"input={in_name}, "
            f"output={out_name}, "
            f"children={list(self._children)})"
        )

    # --- state / clone ------------------------------------------------------
    def state(self) -> AgentState:
        """Snapshot declared state (role, task, rules, examples, config, tree).

        Does not capture strands internals or the computation graph; those
        are rebuilt by `build()`. Children are walked recursively and keyed
        by the attribute name under which they were attached.
        """
        cfg = self.config.model_copy(deep=True) if self.config is not None else None
        # Thawed snapshots may contain intentionally redacted provider keys.
        # Construct without re-validation so state()/hash_content still work.
        return AgentState.model_construct(
            class_name=type(self).__name__,
            name=self.name,
            role=self.role,
            task=self.task,
            style=self.style,
            context=self.context,
            rules=list(self.rules),
            examples=[e.model_dump(mode="json") for e in self.examples],
            config=cfg,
            input_type_name=self.input.__name__,  # type: ignore[union-attr]
            output_type_name=self.output.__name__,  # type: ignore[union-attr]
            children={
                name: child.state() for name, child in self._children.items()
            },
        )

    def load_state(self, s: AgentState) -> None:
        """Overwrite declared state in place from an `AgentState` snapshot.

        Structural fields (`input`/`output` types) are not modified — they
        are part of the contract, not state; construct a new agent if you
        want to change them. Resets `_built` and `_graph`; the caller must
        `build()` again before `invoke`.
        """
        if set(s.children.keys()) != set(self._children.keys()):
            raise BuildError(
                "prompt_incomplete",
                (
                    "load_state shape mismatch: expected children "
                    f"{sorted(self._children)}, got {sorted(s.children)}"
                ),
                agent=type(self).__name__,
            )

        self.role = s.role
        self.task = s.task
        self.style = s.style
        self.context = s.context
        self.name = s.name or self.name or type(self).__name__
        self.rules = list(s.rules)
        self.examples = [
            Example(
                input=self.input.model_validate(e["input"]),  # type: ignore[union-attr]
                output=self.output.model_validate(e["output"]),  # type: ignore[union-attr]
            )
            for e in s.examples
        ]
        self.config = (
            s.config.model_copy(deep=True) if s.config is not None else None
        )

        for name, child_state in s.children.items():
            self._children[name].load_state(child_state)

        object.__setattr__(self, "_built", False)
        object.__setattr__(self, "_graph", None)

    def state_dict(self) -> AgentState:
        """PyTorch-style alias for :meth:`state`."""
        return self.state()

    def load_state_dict(self, sd: AgentState) -> None:
        """PyTorch-style alias for :meth:`load_state`."""
        self.load_state(sd)

    def clone(self, *, context: str | None = None) -> Self:
        """Return a fresh, unbuilt deep copy of this agent.

        Preserves declared Agent state (role, task, context, rules,
        examples, config, input/output types) and the composite routing
        structure. Composite subclasses' extra attributes (e.g.
        `Sequential._stages`, `Parallel._keys`/`_combine`) are deep-copied
        with cloned children substituted for their originals.
        Default-forward leaves skip the strands-owned internals written
        by `build()`; the caller rebuilds.

        Pass ``context=...`` to override the cloned agent's context
        string — useful for algorithms that instantiate component
        defaults with a per-instance context.

        Shared children (the same Agent attached under multiple attribute
        names) are cloned once and reattached under each name, preserving
        the parent's sharing topology.
        """
        new = type(self).__new__(type(self))
        object.__setattr__(new, "_children", {})
        object.__setattr__(new, "_built", False)
        object.__setattr__(new, "_graph", None)
        object.__setattr__(new, "_requires_grad_overrides", {})
        object.__setattr__(new, "_configuration_constraint", self._configuration_constraint)
        object.__setattr__(new, "_forward_pre_hooks", [])
        object.__setattr__(new, "_forward_hooks", [])
        object.__setattr__(new, "_backward_hooks", [])

        new.role = self.role
        new.task = self.task
        new.style = self.style
        new.context = context if context is not None else self.context
        new.name = self.name
        new.rules = list(self.rules)
        new.examples = [e.model_copy(deep=True) for e in self.examples]
        new.config = (
            self.config.model_copy(deep=True) if self.config is not None else None
        )
        new.input = self.input
        new.output = self.output

        memo: dict[int, Any] = {}
        for name, child in self._children.items():
            cloned = memo.get(id(child))
            if cloned is None:
                cloned = child.clone()
                memo[id(child)] = cloned
            setattr(new, name, cloned)

        # Composite subclasses may hold non-Agent routing state
        # (Sequential._stages, Parallel._keys, Parallel._combine, etc.) that
        # references children. Deep-copy it with the clone memo so those
        # references point at the new clones. The Strands runner is
        # rebuilt by the next `abuild()`, never deep-copied.
        if type(self).forward is not Agent.forward:
            _known = {
                "role", "task", "style", "context", "name", "rules", "examples", "config",
                "input", "output",
                "_children", "_built", "_graph", "_runner",
                "_requires_grad_overrides",
                "_forward_pre_hooks", "_forward_hooks", "_backward_hooks",
            }
            for name, value in self.__dict__.items():
                if name in _known or isinstance(value, Agent):
                    continue
                object.__setattr__(new, name, copy.deepcopy(value, memo))

        return new

    # --- content addressing -------------------------------------------------
    @property
    def hash_content(self) -> str:
        """16-hex-char SHA-256 over the agent's declared state.

        Two agents with the same `hash_content` render to the same
        system prompt on every leaf, regardless of object identity.
        Stable across `.build()` (build does not mutate declared state);
        changes after any mutation of role/task/rules/examples/config.
        """
        return hash_json(self.state().model_dump(mode="json"))

    # --- invocation hooks (overridable) -------------------------------------
    def forward_in(self, x: In) -> In:
        """Runs before `forward`. Override to mutate or redact `x`."""
        return x

    def forward_out(self, x: In, y: Out) -> Out:
        """Runs after `forward`. Override to repair or moderate `y`."""
        return y

    # --- parameter surface --------------------------------------------------
    def _iter_declared_parameters(
        self, *, element_wise: bool = False
    ) -> Iterator[tuple[str, "Parameter[Any]"]]:
        """Yield `(local_path, Parameter)` pairs for this agent's trainable fields.

        Single source of truth for the default parameter set. List-valued
        fields (`rules`, `examples`) yield a single list-level param by
        default; pass ``element_wise=True`` to yield one param per element.

        Parameters are constructed fresh on each call (they are thin read-
        through views). ``requires_grad`` is populated from
        ``_requires_grad_overrides`` when the exact local path is present.
        """
        from ..optim.parameter import (
            CategoricalParameter,
            ConfigurationParameter,
            ExampleListParameter,
            FloatParameter,
            Parameter,
            RuleListParameter,
            TextParameter,
        )

        overrides: dict[str, bool] = self._requires_grad_overrides

        def _mk(
            path: str,
            ctor: Any,
            kind: str,
            constraint: Any = None,
        ) -> tuple[str, "Parameter[Any]"]:
            p = ctor.from_agent(self, path, kind, constraint=constraint)
            if path in overrides:
                p.requires_grad = overrides[path]
            return path, p

        yield _mk("role", TextParameter, "role")
        yield _mk("task", TextParameter, "task")
        yield _mk("style", TextParameter, "style")

        if element_wise:
            for i in range(len(self.rules)):
                yield _mk(f"rules[{i}]", TextParameter, "rule_i")
        else:
            yield _mk("rules", RuleListParameter, "rules")

        if element_wise:
            for i in range(len(self.examples)):
                yield _mk(f"examples[{i}]", Parameter, "example_i")
        else:
            yield _mk("examples", ExampleListParameter, "examples")

        if self.config is not None:
            if overrides.get("config", False):
                yield _mk(
                    "config",
                    ConfigurationParameter,
                    "configuration",
                    constraint=self._configuration_constraint,
                )
            else:
                yield _mk(
                    "config.sampling.temperature", FloatParameter, "temperature"
                )
                if self.config.sampling.top_p is not None:
                    yield _mk(
                        "config.sampling.top_p", FloatParameter, "top_p"
                    )
                yield _mk("config.model", CategoricalParameter, "model")
                yield _mk("config.backend", CategoricalParameter, "backend")
                yield _mk(
                    "config.io.renderer", CategoricalParameter, "renderer"
                )

    def parameters(
        self, *, recurse: bool = True, element_wise: bool = False
    ) -> Iterator["Parameter[Any]"]:
        """Iterate over this agent's `Parameter`s (and descendants' when recursing).

        Children are walked in attribute-insertion order (the order they
        were assigned onto the composite).
        """
        for _, p in self._iter_declared_parameters(element_wise=element_wise):
            yield p
        if recurse:
            for child in self._children.values():
                yield from child.parameters(recurse=True, element_wise=element_wise)

    def named_parameters(
        self, *, recurse: bool = True, element_wise: bool = False
    ) -> Iterator[tuple[str, "Parameter[Any]"]]:
        """Iterate `(qualified_path, Parameter)` pairs over self and descendants.

        Recursion prefixes each child's paths with the attribute name it was
        attached under, dot-separated (e.g. ``stage_0.role``).
        """
        for path, p in self._iter_declared_parameters(element_wise=element_wise):
            yield path, p
        if recurse:
            for child_name, child in self._children.items():
                for sub_path, p in child.named_parameters(
                    recurse=True, element_wise=element_wise
                ):
                    yield f"{child_name}.{sub_path}", p

    def trainable_parameters(self) -> Iterator["Parameter[Any]"]:
        """Subset of `parameters()` where ``requires_grad`` is ``True``."""
        for p in self.parameters():
            if p.requires_grad:
                yield p

    def _apply_field_flag(
        self, field: str, value: bool, *, strict: bool
    ) -> None:
        """Write ``_requires_grad_overrides[path] = value`` for a local field.

        Sampling fields (``temperature``, ``top_p``) and the whole-config
        flag (``config``) require ``config`` to be set. ``strict=True``
        raises ``KeyError`` when it isn't; ``False`` silently skips (used
        for broadcast recursion over composites).
        """
        path = _LOCAL_FIELD_TO_PATH[field]
        if field in ("temperature", "top_p", "config") and self.config is None:
            if strict:
                raise KeyError(
                    f"{field!r}: {type(self).__name__} has no config"
                )
            return
        self._requires_grad_overrides[path] = value

    def _set_requires_grad(
        self,
        value: bool,
        *,
        role: bool = False,
        task: bool = False,
        style: bool = False,
        rules: bool = False,
        examples: bool = False,
        temperature: bool = False,
        top_p: bool = False,
        config: bool = False,
        recurse: bool = True,
        _strict: bool = True,
        **per_path: bool,
    ) -> None:
        """Shared core for `mark_trainable` / `freeze_parameters`.

        Boolean kwargs select which local fields to write; ``value`` (the
        method's target — ``True`` for `mark_trainable`, ``False`` for
        `freeze_parameters`) is written into ``_requires_grad_overrides``
        for each selected path. Per-path kwargs supplied via ``**per_path``
        use the same truthy-selects convention: the key names an absolute
        path from ``self`` to a descendant's local field, and a truthy
        value marks it as selected. The method's ``value`` is applied.
        When ``recurse=True``, the boolean-kwarg set is broadcast to every
        descendant; per-path selections apply only at their target and are
        evaluated after broadcast (so they win when both hit the same
        path).
        """
        flags = {
            "role": role, "task": task, "style": style,
            "rules": rules, "examples": examples,
            "temperature": temperature, "top_p": top_p,
            "config": config,
        }
        for field, on in flags.items():
            if on:
                self._apply_field_flag(field, value, strict=_strict)

        if recurse:
            for child in self._children.values():
                child._set_requires_grad(
                    value,
                    role=role, task=task, style=style,
                    rules=rules, examples=examples,
                    temperature=temperature, top_p=top_p,
                    config=config,
                    recurse=True, _strict=False,
                )

        for path, selected in per_path.items():
            if selected:
                self._apply_per_path(path, value)

    def _apply_per_path(self, path: str, value: bool) -> None:
        if "." in path:
            prefix, rest = path.split(".", 1)
            if prefix in self._children:
                self._children[prefix]._apply_per_path(rest, value)
                return
            raise KeyError(
                f"unknown per-path {path!r}: no child named {prefix!r} on "
                f"{type(self).__name__}"
            )
        if path not in _LOCAL_FIELD_TO_PATH:
            raise KeyError(
                f"unknown per-path field {path!r}; expected one of "
                f"{sorted(_LOCAL_FIELD_TO_PATH)}"
            )
        self._apply_field_flag(path, value, strict=True)

    def mark_trainable(
        self,
        *,
        role: bool = False,
        task: bool = False,
        style: bool = False,
        rules: bool = False,
        examples: bool = False,
        temperature: bool = False,
        top_p: bool = False,
        config: bool = False,
        recurse: bool = True,
        **per_path: bool,
    ) -> None:
        """Flip selected fields to ``requires_grad=True``.

        Field-name kwargs (``role=True``, ``task=True``, ...) write to this
        agent's override table. Per-path kwargs passed via ``**per_path``
        (e.g. ``**{"stage_0.role": True}``) name a specific descendant
        field; a truthy value selects it. ``recurse=True`` broadcasts the
        selected field names to every descendant (silently skipping fields
        that don't apply, e.g. ``temperature`` on a composite with no
        ``config``).

        ``config=True`` opts the whole `Configuration` block into a single
        `ConfigurationParameter`; in that mode the leaf-level config
        flags (``temperature``, ``top_p``, ``model``, ``backend``,
        ``renderer``) are silently overridden so the optimizer only sees
        one decomposition.
        """
        self._set_requires_grad(
            True,
            role=role, task=task, style=style,
            rules=rules, examples=examples,
            temperature=temperature, top_p=top_p,
            config=config, recurse=recurse,
            **per_path,
        )

    def freeze_parameters(
        self,
        *,
        role: bool = False,
        task: bool = False,
        style: bool = False,
        rules: bool = False,
        examples: bool = False,
        temperature: bool = False,
        top_p: bool = False,
        config: bool = False,
        recurse: bool = True,
        **per_path: bool,
    ) -> None:
        """Flip selected fields to ``requires_grad=False`` (same kwargs as
        `mark_trainable`)."""
        self._set_requires_grad(
            False,
            role=role, task=task, style=style,
            rules=rules, examples=examples,
            temperature=temperature, top_p=top_p,
            config=config, recurse=recurse,
            **per_path,
        )

    def unfreeze_parameters(
        self,
        *,
        role: bool = False,
        task: bool = False,
        style: bool = False,
        rules: bool = False,
        examples: bool = False,
        temperature: bool = False,
        top_p: bool = False,
        config: bool = False,
        recurse: bool = True,
        **per_path: bool,
    ) -> None:
        """Alias for `mark_trainable` — included for PyTorch muscle memory."""
        self.mark_trainable(
            role=role, task=task, style=style,
            rules=rules, examples=examples,
            temperature=temperature, top_p=top_p,
            config=config, recurse=recurse,
            **per_path,
        )

    def set_configuration_constraint(
        self, constraint: "Any | None"
    ) -> None:
        """Attach a ``ConfigurationConstraint`` consulted by `ConfigurationParameter`.

        The constraint flows into the parameter via
        ``ConfigurationParameter.from_agent`` whenever
        ``mark_trainable(config=True)`` is set. Pass ``None`` to clear.
        """
        object.__setattr__(self, "_configuration_constraint", constraint)

    # --- forward / backward hooks (registered) ------------------------------
    def register_forward_pre_hook(
        self, fn: Callable[["Agent[Any, Any]", Any], Any]
    ) -> Handle:
        """Register a synchronous callback run before ``forward``.

        Signature: ``fn(agent, input) -> input | None``. If the return is
        not ``None``, it replaces the input that ``forward`` will see.
        Runs *before* the overridable ``forward_in`` hook. Multiple hooks
        fire in registration order. Hooks do not run when an
        ``inference_mode()`` context is active, nor during ``build()``
        symbolic tracing.
        """
        self._forward_pre_hooks.append(fn)
        return Handle(self._forward_pre_hooks, fn)

    def register_forward_hook(
        self, fn: Callable[["Agent[Any, Any]", Any, Any], None]
    ) -> Handle:
        """Register a synchronous callback run after ``forward``.

        Signature: ``fn(agent, input, output) -> None``. Any return value
        is ignored. Runs *after* the overridable ``forward_out`` hook.
        Skipped under ``inference_mode()`` and during symbolic tracing.
        """
        self._forward_hooks.append(fn)
        return Handle(self._forward_hooks, fn)

    def register_backward_hook(
        self, fn: Callable[["Agent[Any, Any]", Any], Any]
    ) -> Handle:
        """Register a synchronous callback for gradient propagation.

        Signature: ``fn(agent, grad) -> TextualGradient | None``. Wave 3-1
        will invoke these during ``tape.backward()``; this wave stores the
        callbacks only.
        """
        self._backward_hooks.append(fn)
        return Handle(self._backward_hooks, fn)

    # --- composition --------------------------------------------------------
    def __rshift__(self, other: "Agent[Any, Any]") -> "Agent[Any, Any]":
        """`a >> b` constructs a `Sequential(a, b)`; flattens when chained."""
        from .flow import Sequential

        if isinstance(self, Sequential):
            return Sequential(
                *self._stages, other, input=self.input, output=other.output
            )
        return Sequential(self, other, input=self.input, output=other.output)

    # --- message formatting (overridable) -----------------------------------
    def format_system_message(self) -> str | list[dict[str, str]]:
        """Render the agent's static contract into a system message.

        Default: XML-tagged sections (``<role>``, ``<task>``, ``<rules>``,
        ``<examples>``, ``<output_schema>``). The renderer is selected by
        the class-level ``renderer`` override, falling back to
        ``config.io.renderer`` (``"xml"``, ``"markdown"``, or ``"chat"``).
        The ``"chat"`` renderer returns a list of ``{"role","content"}``
        messages; the others return a single string. Override this
        method for a fully custom wire format.
        """
        mode = type(self).renderer or (
            self.config.io.renderer if self.config is not None else "xml"
        )
        if mode == "markdown":
            return render.markdown.render_system(self)
        if mode == "chat":
            return render.chat.render_system(self)
        return render.xml.render_system(self)

    def format_user_message(self, x: In) -> str:
        """Render a per-call input into the user-message string.

        Default: ``<input>`` block with one ``<field>`` per Pydantic
        field *without* the ``operad.system`` marker. Fields tagged as
        system (see :mod:`operad.core.fields`) are routed to
        :meth:`format_system_input` instead so they can be appended to
        the cached system prompt.
        """
        return render.render_input(x)

    def format_system_input(self, x: In) -> str:
        """Render system-flagged input fields for the per-call system prompt.

        Returns ``""`` when no field on ``x`` carries the
        ``operad.system`` marker — which is the full back-compat case.
        The renderer is selected the same way as
        :meth:`format_system_message` (class-level ``renderer`` override
        or ``config.io.renderer``). Chat mode returns the single content
        string extracted from its message list so the composer stays
        textual.
        """
        mode = type(self).renderer or (
            self.config.io.renderer if self.config is not None else "xml"
        )
        if mode == "markdown":
            return render.markdown.render_system_input(x)
        if mode == "chat":
            msgs = render.chat.render_system_input(x)
            return "\n\n".join(m.get("content", "") for m in msgs)
        return render.xml.render_system_input(x)

    def _compose_system_for_call(self, x: In) -> str:
        """Compose the per-call system prompt: static base + system-input block.

        Returns the static base verbatim when no field is system-flagged
        — so inputs without the marker produce byte-identical bytes to
        pre-refactor behaviour. Otherwise appends ``"\\n\\n"`` + the
        system-input block. The prefix up to ``len(base)`` stays stable
        across calls that share the same static contract, which is what
        provider prompt caching hashes.
        """
        base = _system_to_str(self.format_system_message())
        extra = self.format_system_input(x)
        if not extra:
            return base
        if not base:
            return extra
        return f"{base}\n\n{extra}"

    # --- introspection ------------------------------------------------------
    def operad(self, *, file: TextIO | None = None) -> None:
        """Print every default-forward leaf's rendered system prompt.

        Walks the agent tree and prints, for each leaf that delegates to
        the default `Agent.forward`, the full system message produced by
        `format_system_message()` — role, task, rules, examples, and
        output schema. Composites and custom-forward leaves are skipped:
        neither surfaces a prompt the model will see.

        Zero tokens are generated; no observer events are emitted. Use
        as a sanity check before `abuild()` and before any billable call.
        """
        out = sys.stdout if file is None else file
        rendered = self.operad_dump()
        if not rendered:
            print("(no default-forward leaves)", file=out)
            return
        for i, (path, prompt) in enumerate(rendered.items()):
            if i > 0:
                print("", file=out)
            print(f"=== {path} ===", file=out)
            print(prompt, file=out)

    def operad_dump(self) -> dict[str, str | list[dict[str, str]]]:
        """Return `{qualified_path: rendered_system_prompt}` for every leaf.

        Machine-readable sibling of `operad()`. Same skip rules: only
        default-forward leaves appear. Values are whatever
        `format_system_message()` returns (``str`` for xml/markdown,
        ``list[dict]`` for the chat renderer).
        """
        result: dict[str, str | list[dict[str, str]]] = {}
        for path, node in _labelled_tree(self):
            if node._children:
                continue
            if type(node).forward is not Agent.forward:
                continue
            result[path] = node.format_system_message()
        return result

    def diff(self, other: "Agent[Any, Any]") -> AgentDiff:
        """Compare another agent to this one; `self` is the reference ("before").

        Returns an `AgentDiff` covering role/task (string-level),
        rules (line-level), examples (list add/remove), config
        (field-level), and structural changes (child added / removed).
        Neither agent is mutated; the comparison runs over `state()`
        snapshots.
        """
        return diff_states(self.state(), other.state())

    def _repr_html_(self) -> str:
        """Rich HTML rendering for Jupyter / marimo / VS Code notebooks.

        When built, renders the Mermaid source in a `<pre class="mermaid">`
        block; otherwise falls back to an escaped `<pre>` summary. Plain
        text environments continue to use `__repr__`.
        """
        graph = self.__dict__.get("_graph")
        if self._built and graph is not None:
            return f'<pre class="mermaid">{_html.escape(self.graph_mermaid())}</pre>'
        return f"<pre>{_html.escape(repr(self))}</pre>"

    def graph_json(self) -> dict[str, Any]:
        """Return the built graph as JSON."""
        graph = self.__dict__.get("_graph")
        if graph is None:
            raise BuildError(
                "not_built",
                "agent graph is missing; call .abuild() first",
                agent=self.name,
            )
        from .graph import to_json as _graph_to_json

        return _graph_to_json(graph)

    def graph_mermaid(self) -> str:
        """Return the built graph as Mermaid source."""
        graph = self.__dict__.get("_graph")
        if graph is None:
            raise BuildError(
                "not_built",
                "agent graph is missing; call .abuild() first",
                agent=self.name,
            )
        flow = _leaf_flow(self)

        def _escape(label: str) -> str:
            return label.replace('"', "'")

        lines: list[str] = ["flowchart LR"]
        node_ids = {path: f"n{i}" for i, path in enumerate(flow.nodes)}
        for path, agent in flow.nodes.items():
            lines.append(f'    {node_ids[path]}["{_escape(agent.name)}"]')

        seen: set[tuple[str, str, str]] = set()
        for src, dst, payload in flow.edges:
            label = _type_name(payload)
            key = (src, dst, label)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f'    {node_ids[src]} -->|"{_escape(label)}"| {node_ids[dst]}'
            )
        return "\n".join(lines)

    def graph_outline(self) -> str:
        """Return a repository-style tree of leaf agents."""
        graph = self.__dict__.get("_graph")
        if graph is None:
            raise BuildError(
                "not_built",
                "agent graph is missing; call .abuild() first",
                agent=self.name,
            )
        flow = _leaf_flow(self)

        root = _OutlineNode()
        for path, agent in flow.nodes.items():
            if path == self.name and agent is self and not self._children:
                continue
            segments = _outline_segments(self.name, path, flow.loops)
            node = root
            for seg in segments:
                child = node.branches.get(seg)
                if child is None:
                    child = _OutlineNode()
                    node.branches[seg] = child
                    node.order.append(("branch", seg))
                node = child
            node.order.append(("leaf", agent.name))

        lines: list[str] = [self.name]

        def _render(node: _OutlineNode, prefix: str) -> None:
            for idx, (kind, label) in enumerate(node.order):
                is_last = idx == len(node.order) - 1
                branch = "└── " if is_last else "├── "
                lines.append(f"{prefix}{branch}{label}")
                if kind == "branch":
                    child_prefix = prefix + ("    " if is_last else "│   ")
                    _render(node.branches[label], child_prefix)

        _render(root, "")
        return "\n".join(lines)

    def _apply_default_sampling(self) -> None:
        if self.config is None or not type(self).default_sampling:
            return
        from .config import Sampling
        user_set = self.config.sampling.model_fields_set
        fill = {
            k: v
            for k, v in type(self).default_sampling.items()
            if k not in user_set and k in Sampling.model_fields
        }
        if fill:
            new_sampling = self.config.sampling.model_copy(update=fill)
            self.config = self.config.model_copy(update={"sampling": new_sampling})

    def _apply_default_sampling_tree(self) -> None:
        self._apply_default_sampling()
        for child in self._children.values():
            child._apply_default_sampling_tree()

    def _effective_output_schema(self) -> type[BaseModel]:
        """Return the Pydantic class actually sent to strands as the wire schema.

        Equals ``self.output`` unless ``reasoning_field`` is set, in which
        case a cached subclass is returned with the reasoning field declared
        first so the model commits its reasoning before the typed answer.
        """
        if not self.reasoning_field or self.output is None:
            return self.output  # type: ignore[return-value]
        return _wrap_with_reasoning(self.output, self.reasoning_field)

    def _build_transient_runner(
        self, system_prompt: str | None
    ) -> "StrandsRunner | None":
        """Build a fresh `StrandsRunner` for one invoke, sharing the model.

        When ``stateless`` is True (default) every ``forward`` call routes
        through one of these transients so concurrent fan-out on a single
        operad Agent doesn't race on a shared system prompt. The
        transient lives only for the duration of the call and carries
        the per-call composed system prompt.

        Returns ``None`` when ``self._runner`` hasn't been set — a leaf
        whose ``_init_runner`` was skipped (e.g. tests that bypass
        ``abuild``). The caller falls back to mutating ``self._runner``
        for that single call; reentrancy still holds in the normal
        built-leaf case.
        """
        if self._runner is None:
            return None
        return StrandsRunner(
            model=self._runner.model,
            system_prompt=system_prompt,
        )

    # --- default leaf forward ------------------------------------------------
    async def forward(self, x: In) -> Out:
        """Default leaf behavior: single Strands call with structured output.

        The system prompt was wired at ``build()`` time
        (see ``operad.core.build._init_runner``); here we only render
        the per-call user turn. Composite agents override this.

        When ``self.config.io.stream`` is True, dispatches to the streaming
        path: consumes strands' ``stream_async`` iterator, emits ``chunk``
        observer events for each mid-run token, and parses the accumulated
        text back to ``self.output``. The return shape is unchanged.

        When ``config.io.structuredio`` is ``False``, the call omits
        ``structured_output_model`` and parses the model's textual
        response as JSON against ``self.output``. Use this path for
        backends without native structured output or when the caller
        wants to see exactly what the model produced.
        """
        if self.config is not None and self.config.io.stream:
            return await self._stream_forward(x, self._default_chunk_sink)

        from ..runtime.observers.base import _RETRY_META

        meta = _RETRY_META.get()

        def _record(attempt: int, last: BaseException | None) -> None:
            if meta is not None:
                meta["retries"] = attempt - 1
                meta["last_error"] = None if last is None else repr(last)

        structuredio = self.config.io.structuredio  # type: ignore[union-attr]
        user_msg = self.format_user_message(x)
        composed_system = self._compose_system_for_call(x) or None
        effective_out = self._effective_output_schema()
        stateless = self.stateless

        async with _acquire_slot(self.config) as slot:  # type: ignore[arg-type]
            async def _call() -> Any:
                transient = (
                    self._build_transient_runner(composed_system)
                    if stateless
                    else None
                )
                if transient is not None:
                    if structuredio:
                        return await transient.invoke_async(
                            user_msg,
                            structured_output_model=effective_out,
                        )
                    return await transient.invoke_async(user_msg)
                # Stateful path (or fallback when no runner is set):
                # mutate the persistent runner so strands carries
                # conversation history across calls. Concurrent fan-out
                # on a stateless=False agent is undefined by contract.
                if self._runner is None:
                    raise BuildError(
                        "not_built",
                        f"{type(self).__name__} has no runner; call abuild() first",
                        agent=type(self).__name__,
                    )
                self._runner.system_prompt = composed_system
                if structuredio:
                    return await self._runner.invoke_async(
                        user_msg,
                        structured_output_model=effective_out,
                    )
                return await self._runner.invoke_async(user_msg)

            result: Any = None
            try:
                result = await _with_retry(
                    _call,
                    max_retries=self.config.resilience.max_retries,
                    backoff_base=self.config.resilience.backoff_base,
                    timeout=self.config.resilience.timeout,
                    on_attempt=_record,
                )
            finally:
                slot.settle(tokens=_extract_tokens(result))
        if structuredio:
            raw = result.structured_output
            if self.reasoning_field is not None:
                return _strip_reasoning(  # type: ignore[return-value]
                    raw, self.output, self.reasoning_field  # type: ignore[arg-type]
                )
            return raw  # type: ignore[no-any-return]
        text = _extract_text(result)
        try:
            parsed = effective_out.model_validate_json(text)
        except Exception as e:
            raise BuildError(
                "output_mismatch",
                f"could not parse textual response as {effective_out.__name__}: {e}",
                agent=type(self).__name__,
            ) from e
        if self.reasoning_field is not None:
            return _strip_reasoning(  # type: ignore[return-value]
                parsed, self.output, self.reasoning_field  # type: ignore[arg-type]
            )
        return parsed  # type: ignore[return-value]

    async def _default_chunk_sink(self, i: int, piece: str) -> None:
        from ..runtime.observers import base as _obs

        run_id = _obs._RUN_ID.get() or ""
        entry = _obs._PATH_STACK.get()
        path = entry[1] if entry else self.name
        await _obs.registry.notify(
            _obs.AgentEvent(
                run_id, path, "chunk", None, None, None,
                time.time(), None,
                {"chunk_index": i, "text": piece},
            )
        )

    async def _stream_forward(
        self,
        x: In,
        on_chunk: Callable[[int, str], Awaitable[None]],
    ) -> Out:
        """Consume strands' streaming API; deliver each token to `on_chunk`.

        Parses the final structured output either from a ``result`` event
        (if strands surfaces one) or by accumulating ``data`` pieces and
        running ``self.output.model_validate_json`` as a fallback. Coordinate
        with feature-structuredio (E-3): once that merges, this parse path
        should defer to the shared parser.
        """
        accumulated: list[str] = []
        idx = 0
        structured: Any = None
        final_result: Any = None
        composed_system = self._compose_system_for_call(x) or None
        effective_out = self._effective_output_schema()
        user_msg = self.format_user_message(x)
        transient = (
            self._build_transient_runner(composed_system)
            if self.stateless
            else None
        )
        if transient is not None:
            stream_source: Any = transient
        else:
            if self._runner is None:
                raise BuildError(
                    "not_built",
                    f"{type(self).__name__} has no runner; call abuild() first",
                    agent=type(self).__name__,
                )
            self._runner.system_prompt = composed_system
            stream_source = self._runner
        async with _acquire_slot(self.config) as slot:  # type: ignore[arg-type]
            try:
                async for event in stream_source.stream_async(
                    user_msg,
                    structured_output_model=effective_out,
                ):
                    if not isinstance(event, dict):
                        continue
                    piece = event.get("data")
                    if isinstance(piece, str) and piece:
                        accumulated.append(piece)
                        await on_chunk(idx, piece)
                        idx += 1
                    result = event.get("result")
                    if result is not None:
                        final_result = result
                        maybe = getattr(result, "structured_output", None)
                        if maybe is not None:
                            structured = maybe
            finally:
                slot.settle(tokens=_extract_tokens(final_result))
        if structured is not None:
            if self.reasoning_field is not None:
                return _strip_reasoning(  # type: ignore[return-value]
                    structured, self.output, self.reasoning_field  # type: ignore[arg-type]
                )
            return structured  # type: ignore[no-any-return]
        text = "".join(accumulated)
        try:
            parsed = effective_out.model_validate_json(text)
        except Exception as e:
            raise BuildError(
                "output_mismatch",
                f"streamed text did not parse as {effective_out.__name__}: {e}",
                agent=type(self).__name__,
            ) from e
        if self.reasoning_field is not None:
            return _strip_reasoning(  # type: ignore[return-value]
                parsed, self.output, self.reasoning_field  # type: ignore[arg-type]
            )
        return parsed  # type: ignore[return-value]

    # --- run-context helpers ----------------------------------------------

    def _compute_path(self) -> str:
        from ..runtime.observers import base as _obs

        parent_entry = _obs._PATH_STACK.get()
        if parent_entry is None:
            return self.name
        parent_agent, parent_path = parent_entry
        attr = _attr_name_hint(parent_agent, self) or self.name
        return f"{parent_path}.{attr}"

    def _enter_run(
        self, path: str, *, track_retry: bool
    ) -> tuple[bool, str, float, float, str, dict[str, Any], dict[str, Any], tuple[Any, Any, Any, Any | None]]:
        """Set up per-run ContextVars and return the run frame.

        Returns ``(is_root, run_id, started, started_wall, graph_hash,
        start_meta, retry_meta, tokens)`` where ``tokens`` is the tuple
        ``(tok_r, tok_p, tok_g, tok_m)`` to be handed to `_exit_run`.
        ``tok_m`` is ``None`` when ``track_retry`` is False (streaming).
        """
        from ..runtime.observers import base as _obs

        is_root = _obs._RUN_ID.get() is None
        run_id = _obs._RUN_ID.get() or uuid.uuid4().hex
        started_wall = time.time()
        started = time.monotonic()

        graph_hash = _RUN_GRAPH_HASH.get()
        tok_g = None
        if is_root:
            graph_hash = _compute_graph_hash(self)
            tok_g = _RUN_GRAPH_HASH.set(graph_hash)
        tok_r = _obs._RUN_ID.set(run_id)
        tok_p = _obs._PATH_STACK.set((self, path))
        retry_meta: dict[str, Any] = {}
        tok_m = _obs._RETRY_META.set(retry_meta) if track_retry else None

        start_meta: dict[str, Any] = {}
        if is_root:
            start_meta["graph"] = _graph_json_or_none(self)
            start_meta["is_root"] = True
            if sys.argv and sys.argv[0]:
                start_meta["script"] = sys.argv[0]
        return is_root, run_id, started, started_wall, graph_hash, start_meta, retry_meta, (tok_r, tok_p, tok_g, tok_m)

    def _exit_run(
        self, tokens: tuple[Any, Any, Any, Any | None]
    ) -> None:
        from ..runtime.observers import base as _obs

        tok_r, tok_p, tok_g, tok_m = tokens
        if tok_m is not None:
            _obs._RETRY_META.reset(tok_m)
        _obs._RUN_ID.reset(tok_r)
        _obs._PATH_STACK.reset(tok_p)
        if tok_g is not None:
            _RUN_GRAPH_HASH.reset(tok_g)

    def validate(self, x: In) -> None:
        """Raise if this agent cannot accept `x`.

        Checks that `build()` has been called and that `x` matches the
        declared `input` type. Single source of truth for input
        pre-flight validation; `invoke`/`stream` call this rather than
        repeating the checks inline.
        """
        if not self._built:
            raise BuildError(
                "not_built",
                "call .build() before .invoke()",
                agent=type(self).__name__,
            )
        if not isinstance(x, self.input):  # type: ignore[arg-type]
            raise BuildError(
                "input_mismatch",
                f"expected {self.input.__name__}, got {type(x).__name__}",  # type: ignore[union-attr]
                agent=type(self).__name__,
            )

    def _check_output(self, y: Any) -> None:
        if not isinstance(y, self.output):  # type: ignore[arg-type]
            raise BuildError(
                "output_mismatch",
                f"forward returned {type(y).__name__}, expected {self.output.__name__}",  # type: ignore[union-attr]
                agent=type(self).__name__,
            )

    # --- framework entry point ----------------------------------------------
    async def invoke(self, x: In) -> OperadOutput[Out]:
        """Validate contract, then run `forward`, wrap in `OperadOutput`.

        When a symbolic tracer is active (during `build()`), this method
        short-circuits into the tracer instead of running real logic.
        """
        tracer = _TRACER.get()
        if tracer is not None:
            response = await tracer.record(self, x)
            return OperadOutput[Any].model_construct(response=response)

        return await self._invoke_envelope(x, executor=self.forward)

    async def _invoke_envelope(
        self,
        x: In,
        *,
        executor: Callable[[In], Awaitable[Out]],
    ) -> OperadOutput[Out]:
        """Shared envelope-construction path for ``invoke`` (and the
        non-streaming half of ``stream``). Handles path computation,
        ContextVar setup, observer notify (start/end/error), the inline
        built/input validation, output type check, envelope build, and
        ContextVar teardown.
        """
        from ..runtime.observers import base as _obs

        path = self._compute_path()
        (
            is_root, run_id, started, started_wall, graph_hash,
            start_meta, retry_meta, tokens,
        ) = self._enter_run(path, track_retry=True)
        algo_parent = _obs._ALGO_RUN_ID.get()
        if algo_parent is not None and not is_root:
            start_meta["parent_run_id"] = algo_parent
        try:
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "start", x, None, None, started_wall, None, start_meta
                )
            )

            self.validate(x)
            run_hooks = not _inference_mode_active()
            if run_hooks:
                for fn in tuple(self._forward_pre_hooks):
                    result = fn(self, x)
                    if result is not None:
                        x = result
            x = self.forward_in(x)
            y = await executor(x)
            y = self.forward_out(x, y)
            if run_hooks:
                for fn in tuple(self._forward_hooks):
                    fn(self, x, y)
            self._check_output(y)

            finished = time.monotonic()
            finished_wall = time.time()
            envelope = self._build_envelope(
                x, y, run_id, path, graph_hash,
                started, started_wall, finished, finished_wall,
            )
            end_meta: dict[str, Any] = {}
            if is_root:
                end_meta["is_root"] = True
                end_meta["output_type"] = _qualified(self.output)  # type: ignore[arg-type]
            end_meta.update(self._dashboard_end_metadata(x))
            end_meta.update(retry_meta)
            if algo_parent is not None and not is_root:
                end_meta["parent_run_id"] = algo_parent
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "end", x, envelope, None, started_wall, finished_wall, end_meta
                )
            )
            return envelope
        except BaseException as e:
            err_meta: dict[str, Any] = {"is_root": True} if is_root else {}
            err_meta.update(retry_meta)
            if algo_parent is not None and not is_root:
                err_meta["parent_run_id"] = algo_parent
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "error", x, None, e, started_wall, time.time(), err_meta
                )
            )
            raise
        finally:
            self._exit_run(tokens)

    async def __call__(self, x: In) -> OperadOutput[Out]:  # type: ignore[override]
        return await self.invoke(x)

    def _build_envelope(
        self,
        x: In,
        y: Out,
        run_id: str,
        path: str,
        graph_hash: str | None,
        started: float,
        started_wall: float,
        finished: float,
        finished_wall: float,
    ) -> OperadOutput[Out]:
        return OperadOutput[Any].model_construct(
            response=y,
            hash_operad_version=OPERAD_VERSION_HASH,
            hash_python_version=PYTHON_VERSION_HASH,
            hash_model=hash_config(self.config),
            hash_prompt=hash_str(
                self._compose_system_for_call(x)
                + "\n\n"
                + self.format_user_message(x)
            ),
            hash_graph=graph_hash,
            hash_input=hash_json(x.model_dump(mode="json")),
            hash_output_schema=hash_schema(self.output),  # type: ignore[arg-type]
            run_id=run_id,
            agent_path=path,
            backend=(self.config.backend if self.config is not None else ""),
            model=(self.config.model if self.config is not None else ""),
            started_at=started_wall,
            finished_at=finished_wall,
            latency_ms=(finished - started) * 1000.0,
        )

    def _dashboard_end_metadata(self, x: In) -> dict[str, Any]:
        examples = [e.model_dump(mode="json") for e in self.examples]
        config = self.config.model_dump(mode="json") if self.config is not None else None
        trainable_paths = sorted(
            path for path, p in self.named_parameters(recurse=True) if p.requires_grad
        )
        parameters = []
        for path, p in self.named_parameters(recurse=True):
            grad = p.grad.model_dump(mode="json") if p.grad is not None else None
            constraint = (
                p.constraint.model_dump(mode="json")
                if isinstance(p.constraint, BaseModel)
                else _json_safe(p.constraint)
            )
            parameters.append(
                {
                    "path": path,
                    "type": type(p).__name__,
                    "value": _json_safe(p.read()),
                    "requires_grad": bool(p.requires_grad),
                    "grad": grad,
                    "constraint": constraint,
                }
            )
        return {
            "class_name": type(self).__name__,
            "name": self.name,
            "kind": "composite" if self._children else "leaf",
            "hash_content": self.hash_content,
            "state_snapshot": self.state().model_dump(mode="json"),
            "role": self.role,
            "task": self.task,
            "rules": list(self.rules),
            "examples": examples,
            "config": config,
            "forward_in_overridden": type(self).forward_in is not Agent.forward_in,
            "forward_out_overridden": type(self).forward_out is not Agent.forward_out,
            "forward_in_doc": inspect.getdoc(type(self).forward_in),
            "forward_out_doc": inspect.getdoc(type(self).forward_out),
            "trainable_paths": trainable_paths,
            "parameters": parameters,
            "prompt_system": self._compose_system_for_call(x),
            "prompt_user": self.format_user_message(x),
        }

    # --- streaming ---------------------------------------------------------
    async def stream(
        self, x: In
    ) -> AsyncIterator[ChunkEvent | OperadOutput[Out]]:
        """Yield ``ChunkEvent``s while the model generates; terminate with the full ``OperadOutput``.

        Equivalent to ``await self.invoke(x)`` when ``config.io.stream`` is
        False or the backend does not support streaming — in which case
        exactly one ``OperadOutput`` is yielded and no ``ChunkEvent``s.

        Retry interaction: if a retry fires mid-stream, v1 re-emits the
        whole stream under a new ``run_id``. Downstream consumers must
        key on ``run_id``.
        """
        if self.config is None or not self.config.io.stream:
            yield await self.invoke(x)
            return

        from ..runtime.observers import base as _obs

        path = self._compute_path()
        (
            is_root, run_id, started, started_wall, graph_hash,
            start_meta, _retry_meta, tokens,
        ) = self._enter_run(path, track_retry=False)
        algo_parent_s = _obs._ALGO_RUN_ID.get()
        if algo_parent_s is not None and not is_root:
            start_meta["parent_run_id"] = algo_parent_s

        # Bounded so a slow consumer applies backpressure to the producer
        # instead of letting the queue grow without bound on a long stream.
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=64)
        _SENTINEL_DONE = object()

        try:
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "start", x, None, None, started_wall, None, start_meta
                )
            )

            self.validate(x)
            x = self.forward_in(x)

            async def on_chunk(i: int, piece: str) -> None:
                await queue.put(ChunkEvent(piece, i, path, run_id))
                await _obs.registry.notify(
                    _obs.AgentEvent(
                        run_id, path, "chunk", None, None, None,
                        time.time(), None,
                        {"chunk_index": i, "text": piece},
                    )
                )

            async def driver() -> None:
                try:
                    y = await self._stream_forward(x, on_chunk)
                    y = self.forward_out(x, y)
                    self._check_output(y)
                    finished = time.monotonic()
                    finished_wall = time.time()
                    envelope = self._build_envelope(
                        x, y, run_id, path, graph_hash,
                        started, started_wall, finished, finished_wall,
                    )
                    await queue.put(envelope)
                except BaseException as e:  # noqa: BLE001
                    await queue.put(e)
                finally:
                    await queue.put(_SENTINEL_DONE)

            task = asyncio.create_task(driver())
            final_envelope: OperadOutput[Any] | None = None
            final_error: BaseException | None = None
            try:
                while True:
                    item = await queue.get()
                    if item is _SENTINEL_DONE:
                        break
                    if isinstance(item, BaseException):
                        final_error = item
                        continue
                    if isinstance(item, ChunkEvent):
                        yield item
                    else:
                        final_envelope = item
                        yield item
            finally:
                await task

            # If the driver task itself raised (e.g. its finally was
            # cancelled mid-put), surface that so we never silently
            # drop an error on the floor.
            if final_error is None and task.done():
                driver_exc = task.exception()
                if driver_exc is not None:
                    final_error = driver_exc

            if final_error is not None:
                raise final_error

            end_meta: dict[str, Any] = {}
            if is_root:
                end_meta["is_root"] = True
                end_meta["output_type"] = _qualified(self.output)  # type: ignore[arg-type]
            end_meta.update(self._dashboard_end_metadata(x))
            if algo_parent_s is not None and not is_root:
                end_meta["parent_run_id"] = algo_parent_s
            finished_wall = time.time()
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "end", x, final_envelope, None,
                    started_wall, finished_wall, end_meta,
                )
            )
        except BaseException as e:
            err_meta: dict[str, Any] = {"is_root": True} if is_root else {}
            if algo_parent_s is not None and not is_root:
                err_meta["parent_run_id"] = algo_parent_s
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "error", x, None, e, started_wall, time.time(), err_meta
                )
            )
            raise
        finally:
            self._exit_run(tokens)

    # --- build --------------------------------------------------------------
    def build(self) -> Self:
        """Symbolically trace the architecture and mark it ready for invoke.

        Synchronous entry point. Use `abuild()` when already inside a
        running event loop.
        """
        from .build import build_agent

        self._apply_default_sampling_tree()
        return build_agent(self)

    async def abuild(self) -> Self:
        """Async variant of `build()` for use inside a running event loop."""
        from .build import abuild_agent

        self._apply_default_sampling_tree()
        return await abuild_agent(self)

    # --- auto-tune ----------------------------------------------------------
    async def auto_tune(
        self,
        dataset: Any,
        metric: Any,
        *,
        kind: Literal["evo", "textgrad", "momentum", "opro", "ape"] = "evo",
        mutations: list[Any] | None = None,
        population_size: int = 8,
        generations: int = 4,
        epochs: int = 1,
        lr: float = 1.0,
        batch_size: int = 4,
        rng: Any = None,
        loss: Any = None,
    ) -> "Agent[In, Out]":
        """Return a copy of this agent tuned to improve `metric` on `dataset`.

        The `kind` keyword dispatches to one of five optimizers. Default
        is evolutionary search — the same behavior this method has
        always had.

        - ``"evo"``: population-based mutation/selection via
          ``operad.optim.EvoGradient``. Respects ``mutations``,
          ``population_size``, ``generations``.
        - ``"textgrad"``: textual-gradient descent via
          ``operad.optim.TextualGradientDescent`` inside a minimal
          ``Trainer`` loop. Respects ``epochs``, ``lr``, ``batch_size``.
        - ``"momentum"``: ``operad.optim.MomentumTextGrad`` instead.
        - ``"opro"``: LLM-as-optimizer over per-parameter history
          (``operad.optim.OPROOptimizer``). Respects ``epochs``.
        - ``"ape"``: sample-and-rank candidate rewrites
          (``operad.optim.APEOptimizer``). Respects ``population_size``
          (mapped to the per-step candidate budget) and ``epochs``.

        ``loss`` overrides the default ``LossFromMetric(metric)`` used
        by the trainer-backed kinds; it is ignored by ``kind="evo"``.

        `dataset` may be a `Dataset`, an iterable of `Entry` objects, or
        an iterable of `(input, expected_output)` tuples.
        """
        if kind == "evo":
            return await self._auto_tune_evo(
                dataset,
                metric,
                mutations=mutations,
                population_size=population_size,
                generations=generations,
                rng=rng,
            )
        if kind in {"textgrad", "momentum", "opro", "ape"}:
            return await self._auto_tune_via_trainer(
                dataset,
                metric,
                kind=kind,
                epochs=epochs,
                lr=lr,
                batch_size=batch_size,
                population_size=population_size,
                loss=loss,
            )
        raise ValueError(
            f"Unknown auto_tune kind={kind!r}; allowed: "
            "evo, textgrad, momentum, opro, ape"
        )

    async def _auto_tune_evo(
        self,
        dataset: Any,
        metric: Any,
        *,
        mutations: list[Any] | None,
        population_size: int,
        generations: int,
        rng: Any,
    ) -> "Agent[In, Out]":
        from ..optim.evo import EvoGradient
        from ..utils.ops import default_mutations

        seed = self.clone()
        await seed.abuild()
        ops = mutations if mutations is not None else default_mutations(seed)
        pairs = _coerce_eval_pairs(dataset)

        optimizer = EvoGradient(
            list(seed.parameters()),
            mutations=ops,
            metric=metric,
            dataset=pairs,
            population_size=population_size,
            rng=rng,
        )
        for _ in range(max(1, int(generations))):
            await optimizer.step()
        return seed

    async def _auto_tune_via_trainer(
        self,
        dataset: Any,
        metric: Any,
        *,
        kind: str,
        epochs: int,
        lr: float,
        batch_size: int,
        population_size: int,
        loss: Any,
    ) -> "Agent[In, Out]":
        from ..data.loader import DataLoader
        from ..optim.ape import APEOptimizer
        from ..optim.loss import LossFromMetric
        from ..optim.momentum import MomentumTextGrad
        from ..optim.opro import OPROOptimizer
        from ..optim.sgd import TextualGradientDescent
        from ..train import Trainer

        seed = self.clone()
        seed.mark_trainable(role=True, task=True, rules=True, recurse=True)
        await seed.abuild()

        ds = _coerce_eval_dataset(dataset)
        loader = DataLoader(ds, batch_size=max(1, int(batch_size)))
        loss_fn = loss if loss is not None else LossFromMetric(metric)
        pairs = _coerce_eval_pairs(dataset)

        params = list(seed.parameters())
        if kind == "textgrad":
            optimizer: Any = TextualGradientDescent(params, lr=lr)
        elif kind == "momentum":
            optimizer = MomentumTextGrad(params, lr=lr)
        elif kind == "opro":
            evaluator = _build_value_evaluator(seed, pairs, metric)
            optimizer = OPROOptimizer(
                params,
                lr=lr,
                objective_metric=metric,
                evaluator=evaluator,
            )
        else:  # kind == "ape"
            evaluator = _build_value_evaluator(seed, pairs, metric)
            optimizer = APEOptimizer(
                params,
                lr=lr,
                evaluator=evaluator,
                k=max(1, int(population_size)),
            )

        trainer = Trainer(seed, optimizer, loss_fn)
        await trainer.fit(loader, epochs=max(1, int(epochs)))
        return seed

    # --- freeze / thaw ------------------------------------------------------
    def freeze(self, path: str) -> None:
        """Persist a built agent to `path` as a single JSON file.

        Skips API keys. Captures declared state, computation graph, each
        leaf's rendered system message, and a pickled blob of composite /
        custom-forward routing state with intra-tree Agent references
        rewritten to a sentinel that `thaw` reattaches.
        """
        from .freeze import freeze_agent

        freeze_agent(self, path)

    @classmethod
    def thaw(cls, path: str) -> "Agent[Any, Any]":
        """Reconstitute a built agent previously written with `freeze`.

        Skips symbolic tracing and per-leaf system-message rendering.
        Raises `BuildError("not_built", ...)` on version mismatch or
        when the frozen root's class is not a subclass of `cls`.
        """
        from .freeze import thaw_agent

        obj = thaw_agent(path)
        if not isinstance(obj, cls):
            raise BuildError(
                "not_built",
                f"frozen class {type(obj).__name__} is not a "
                f"{cls.__name__}",
                agent=cls.__name__,
            )
        return obj

    # --- presentation -------------------------------------------------------
    def summary(self) -> str:
        """One-paragraph overview: class, leaf/composite counts, hashes.

        Format::

            {ClassName}: {n_leaves} leaves, {n_composites} composites, hash_content={short}
              graph_hash={short}  backend={...}  model={...}

        The indented second line is omitted when neither `_graph` nor
        `config` is available.
        """
        n_leaves, n_composites = _count_tree(self)
        line = (
            f"{self.name}: {n_leaves} leaves, {n_composites} composites, "
            f"hash_content={self.hash_content[:8]}"
        )
        extras: list[str] = []
        graph = self.__dict__.get("_graph")
        if graph is not None:
            extras.append(f"graph_hash={_compute_graph_hash(self)[:8]}")
        if self.config is not None:
            backend = getattr(self.config, "backend", "?")
            model = getattr(self.config, "model", "?")
            extras.append(f"backend={backend}")
            extras.append(f"model={model}")
        if not extras:
            return line
        return line + "\n  " + "  ".join(extras)

    def __rich__(self) -> Any:
        """Structured tree rendering for `rich.print(agent)`."""
        from rich.tree import Tree

        in_name = self.input.__name__ if self.input is not None else "?"
        out_name = self.output.__name__ if self.output is not None else "?"
        n_leaves, _ = _count_tree(self)
        header = (
            f"{self.name}[{in_name} → {out_name}] "
            f"· {n_leaves} leaves · hash={self.hash_content[:8]}"
        )
        tree = Tree(header)
        if self.role:
            role_preview = self.role if len(self.role) <= 60 else self.role[:57] + "..."
            tree.add(f"role: {role_preview}")
        graph = self.__dict__.get("_graph")
        if self._built and graph is not None:
            tree.add(f"graph_hash={_compute_graph_hash(self)[:8]}")
        if self.config is not None:
            backend = getattr(self.config, "backend", "?")
            model = getattr(self.config, "model", "?")
            tree.add(f"backend={backend} model={model}")
        return tree

    async def explain(self, x: In) -> None:
        """Run `x`, print scratchpad + output for every leaf in the trace.

        For each default-forward leaf whose `Output` lacks a
        `scratchpad: str` field, temporarily swaps in an augmented
        subclass that prepends one. Prints per leaf::

            === {agent_path} ===
            scratchpad: ...
            output: ...

        Original output classes (and the runner's cached `system_prompt`)
        are restored in a `finally` block.
        """
        from ..runtime.observers.base import registry as _registry
        from ..runtime.trace import TraceObserver

        # Swap Output + re-render the runner's system_prompt on default-
        # forward leaves so that `structured_output_model=self.output`
        # and the cached system message both reflect the scratchpad field.
        swaps: list[tuple[Agent[Any, Any], type[BaseModel], Any]] = []
        try:
            for _path, leaf in _labelled_tree(self):
                if leaf._children:
                    continue
                if type(leaf).forward is not Agent.forward:
                    continue
                if leaf.output is None:
                    continue
                if "scratchpad" in leaf.output.model_fields:
                    continue
                if leaf._runner is None:
                    continue
                original_output = leaf.output
                original_sp = leaf._runner.system_prompt
                leaf.output = _augmented_output(original_output)
                rendered = leaf.format_system_message()
                leaf._runner.system_prompt = _system_to_str(rendered) or None
                swaps.append((leaf, original_output, original_sp))

            observer = TraceObserver()
            _registry.register(observer)
            try:
                await self.invoke(x)
            finally:
                _registry.unregister(observer)

            trace = observer.last()
            if trace is None:
                return
            for step in trace.steps:
                resp = step.output.response
                print(f"=== {step.agent_path} ===")
                scratchpad = getattr(resp, "scratchpad", None)
                if scratchpad is not None:
                    print(f"scratchpad: {scratchpad}")
                data = resp.model_dump(mode="json") if isinstance(resp, BaseModel) else {}
                data.pop("scratchpad", None)
                print(f"output: {data}")
        finally:
            for leaf, original_output, original_sp in swaps:
                leaf.output = original_output
                if leaf._runner is not None:
                    leaf._runner.system_prompt = original_sp


def _coerce_eval_pairs(dataset: Any) -> list[tuple[Any, Any]]:
    """Normalise `auto_tune`'s dataset to `list[tuple[input, expected]]`."""
    from ..benchmark.dataset import Dataset
    from ..benchmark.entry import Entry

    items = list(dataset) if not isinstance(dataset, Dataset) else list(dataset)
    pairs: list[tuple[Any, Any]] = []
    for item in items:
        if isinstance(item, Entry):
            if item.expected_output is None:
                raise ValueError(
                    "auto_tune: every dataset entry must have an expected_output"
                )
            pairs.append((item.input, item.expected_output))
        else:
            inp, exp = item
            pairs.append((inp, exp))
    return pairs


def _coerce_eval_dataset(dataset: Any) -> "Any":
    """Like `_coerce_eval_pairs` but return a `Dataset` for `DataLoader`."""
    from ..benchmark.dataset import Dataset
    from ..benchmark.entry import Entry

    if isinstance(dataset, Dataset):
        return dataset
    entries: list[Entry[Any, Any]] = []
    for item in dataset:
        if isinstance(item, Entry):
            entries.append(item)
        else:
            inp, exp = item
            entries.append(Entry(input=inp, expected_output=exp))
    return Dataset(entries, name="auto_tune", version="v1")


def _build_value_evaluator(
    seed: "Agent[Any, Any]",
    pairs: list[tuple[Any, Any]],
    metric: Any,
) -> Any:
    """Return an ``Evaluator`` closure for OPRO / APE.

    The closure temporarily swaps in a candidate `value` on the given
    `Parameter`, rebuilds `seed`, evaluates against the eval pairs with
    `metric`, and restores the original value before returning the
    mean metric score.
    """
    from ..benchmark.evaluate import evaluate as _evaluate

    async def _evaluator(param: Any, value: Any) -> float:
        old = param.read()
        param.write(value)
        try:
            await seed.abuild()
            report = await _evaluate(seed, pairs, [metric])
        finally:
            param.write(old)
            await seed.abuild()
        return float(report.summary.get(metric.name, float("nan")))

    return _evaluator


def _attr_name_hint(parent: "Agent[Any, Any]", child: "Agent[Any, Any]") -> str | None:
    for name, value in parent._children.items():
        if value is child:
            return name
    return None


def _graph_json_or_none(agent: "Agent[Any, Any]") -> Any:
    graph = getattr(agent, "_graph", None)
    if graph is None:
        return None
    from .graph import to_json as _graph_to_json

    return _graph_to_json(graph)


def _qualified(t: type) -> str:
    from .graph import _qualified_name

    return _qualified_name(t)


def _compute_graph_hash(agent: "Agent[Any, Any]") -> str:
    """Hash the agent's compiled graph if present, else hash its path.

    Algorithms (e.g. `BestOfN`) may invoke a child agent as the "root"
    call of a fresh run; that child carries its own `_graph`. Non-root
    children within a run share the hash set by the outer invocation.
    """
    graph = getattr(agent, "_graph", None)
    if graph is None:
        return hash_str(agent.name)
    from .graph import to_json as _graph_to_json

    return hash_json(_graph_to_json(graph))


def _count_tree(root: "Agent[Any, Any]") -> tuple[int, int]:
    """Return `(n_leaves, n_composites)` walking children with id-dedup."""
    seen: set[int] = set()
    n_leaves = 0
    n_composites = 0
    stack: list[Agent[Any, Any]] = [root]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if node._children:
            n_composites += 1
            stack.extend(node._children.values())
        else:
            n_leaves += 1
    return n_leaves, n_composites


def _augmented_output(out_cls: type[BaseModel]) -> type[BaseModel]:
    """Return a subclass of `out_cls` with a leading `scratchpad: str` field."""
    if "scratchpad" in out_cls.model_fields:
        return out_cls
    fields: dict[str, Any] = {
        "scratchpad": (str, Field(description="Think step-by-step here first.")),
    }
    for name, info in out_cls.model_fields.items():
        fields[name] = (info.annotation, info)
    return create_model(  # type: ignore[call-overload,no-any-return]
        f"{out_cls.__name__}WithScratchpad",
        __base__=out_cls,
        **fields,
    )


def _labelled_tree(
    root: "Agent[Any, Any]",
) -> list[tuple[str, "Agent[Any, Any]"]]:
    """Yield `(qualified_path, agent)` for `root` and every descendant.

    Breadth-first with `id()` de-duplication, matching the walk pattern in
    `operad.core.build._tree`. The root's path is the agent's `name`; each
    descendant's path appends the attribute it was attached under.
    """
    root_name = root.name
    out: list[tuple[str, "Agent[Any, Any]"]] = [(root_name, root)]
    seen: set[int] = {id(root)}
    queue: list[tuple[str, "Agent[Any, Any]"]] = [(root_name, root)]
    while queue:
        parent_path, parent = queue.pop(0)
        for attr, child in parent._children.items():
            if id(child) in seen:
                continue
            seen.add(id(child))
            child_path = f"{parent_path}.{attr}"
            out.append((child_path, child))
            queue.append((child_path, child))
    return out


@dataclass
class _LeafFlowSpec:
    nodes: dict[str, "Agent[Any, Any]"] = field(default_factory=dict)
    edges: list[tuple[str, str, type[Any] | None]] = field(default_factory=list)
    entries: list[tuple[str, type[Any] | None]] = field(default_factory=list)
    exits: list[tuple[str, type[Any] | None]] = field(default_factory=list)
    loops: dict[str, str] = field(default_factory=dict)


@dataclass
class _OutlineNode:
    branches: dict[str, "_OutlineNode"] = field(default_factory=dict)
    order: list[tuple[str, str]] = field(default_factory=list)


def _type_name(t: type[Any] | None) -> str:
    if t is None:
        return "?"
    return getattr(t, "__name__", repr(t))


def _merge_flow(dst: _LeafFlowSpec, src: _LeafFlowSpec) -> None:
    for path, agent in src.nodes.items():
        dst.nodes.setdefault(path, agent)
    dst.edges.extend(src.edges)
    dst.loops.update(src.loops)


def _dedupe_ports(
    ports: list[tuple[str, type[Any] | None]],
) -> list[tuple[str, type[Any] | None]]:
    seen: set[str] = set()
    out: list[tuple[str, type[Any] | None]] = []
    for path, t in ports:
        if path in seen:
            continue
        seen.add(path)
        out.append((path, t))
    return out


def _is_stage_segment(segment: str) -> bool:
    if not segment.startswith("stage_"):
        return False
    return segment[6:].isdigit()


def _outline_segments(
    root_name: str,
    path: str,
    loops: dict[str, str],
) -> list[str]:
    parts = path.split(".")
    if parts and parts[0] == root_name:
        parts = parts[1:]

    current = [root_name]
    out: list[str] = []
    root_loop = loops.get(root_name)
    if root_loop is not None:
        out.append(root_loop)
    for seg in parts:
        current.append(seg)
        loop_label = loops.get(".".join(current))
        if loop_label is not None:
            out.append(loop_label)
        if seg in {"pipeline", "child"}:
            continue
        if _is_stage_segment(seg):
            continue
        if seg.startswith("branch_"):
            branch = seg[len("branch_") :].strip("\"'")
            if branch:
                out.append(branch)
            continue
        if seg.startswith("_"):
            continue
        out.append(seg)
    return out


def _leaf_flow(root: "Agent[Any, Any]") -> _LeafFlowSpec:
    from .flow import Loop, Parallel, Router, Sequential

    def _child_path(
        parent: "Agent[Any, Any]",
        parent_path: str,
        child: "Agent[Any, Any]",
        *,
        fallback: str,
    ) -> str:
        attr = _attr_name_hint(parent, child) or fallback
        return f"{parent_path}.{attr}"

    def _include_leaf(agent: "Agent[Any, Any]", path: str) -> bool:
        if path == root.name:
            return True
        cls_name = type(agent).__name__
        module = getattr(type(agent), "__module__", "")
        if module == "operad.agents.reasoning.react" and cls_name.startswith("_"):
            return False
        return True

    def _compose_linear(
        parts: list[tuple[str, "Agent[Any, Any]"]],
    ) -> _LeafFlowSpec:
        out = _LeafFlowSpec()
        prev_exits: list[tuple[str, type[Any] | None]] = []
        first_entries: list[tuple[str, type[Any] | None]] = []
        for child_path, child in parts:
            part = _build(child, child_path)
            _merge_flow(out, part)
            if not part.entries and not part.exits:
                continue
            if not first_entries:
                first_entries = list(part.entries)
            if prev_exits:
                for src_path, _ in prev_exits:
                    for dst_path, in_t in part.entries:
                        out.edges.append((src_path, dst_path, in_t))
            prev_exits = list(part.exits)
        out.entries = _dedupe_ports(first_entries)
        out.exits = _dedupe_ports(prev_exits)
        return out

    def _build(agent: "Agent[Any, Any]", path: str) -> _LeafFlowSpec:
        if not agent._children:
            if not _include_leaf(agent, path):
                return _LeafFlowSpec()
            return _LeafFlowSpec(
                nodes={path: agent},
                entries=[(path, agent.input)],
                exits=[(path, agent.output)],
            )

        if isinstance(agent, Loop):
            parts: list[tuple[str, Agent[Any, Any]]] = [
                (
                    _child_path(agent, path, stage, fallback=f"stage_{i}"),
                    stage,
                )
                for i, stage in enumerate(agent._stages)
            ]
            out = _compose_linear(parts)
            if out.entries and out.exits:
                for src_path, _ in out.exits:
                    for dst_path, in_t in out.entries:
                        out.edges.append((src_path, dst_path, in_t))
            if agent.n_loops <= 1:
                out.loops[path] = "loop"
            else:
                out.loops[path] = f"loop x{agent.n_loops}"
            return out

        if isinstance(agent, Sequential):
            parts = [
                (
                    _child_path(agent, path, stage, fallback=f"stage_{i}"),
                    stage,
                )
                for i, stage in enumerate(agent._stages)
            ]
            return _compose_linear(parts)

        if isinstance(agent, Parallel):
            out = _LeafFlowSpec()
            entries: list[tuple[str, type[Any] | None]] = []
            exits: list[tuple[str, type[Any] | None]] = []
            for key in agent._keys:
                child = getattr(agent, key)
                child_path = _child_path(agent, path, child, fallback=key)
                part = _build(child, child_path)
                _merge_flow(out, part)
                entries.extend(part.entries)
                exits.extend(part.exits)
            out.entries = _dedupe_ports(entries)
            out.exits = _dedupe_ports(exits)
            return out

        if isinstance(agent, Router):
            out = _LeafFlowSpec()
            router_path = _child_path(agent, path, agent.router, fallback="router")
            router_part = _build(agent.router, router_path)
            _merge_flow(out, router_part)
            out.entries = list(router_part.entries)
            exits: list[tuple[str, type[Any] | None]] = []
            for label, branch in agent._branches.items():
                fallback = agent._branch_attrs.get(label) or f"branch_{label!r}"
                branch_path = _child_path(agent, path, branch, fallback=fallback)
                branch_part = _build(branch, branch_path)
                _merge_flow(out, branch_part)
                for src_path, _ in router_part.exits:
                    for dst_path, in_t in branch_part.entries:
                        out.edges.append((src_path, dst_path, in_t))
                exits.extend(branch_part.exits)
            out.exits = _dedupe_ports(exits or router_part.exits)
            return out

        pipeline = getattr(agent, "pipeline", None)
        if isinstance(pipeline, Agent):
            pipeline_path = _child_path(agent, path, pipeline, fallback="pipeline")
            return _build(pipeline, pipeline_path)

        if len(agent._children) == 1:
            attr, child = next(iter(agent._children.items()))
            return _build(child, f"{path}.{attr}")

        return _compose_linear(
            [(f"{path}.{attr}", child) for attr, child in agent._children.items()]
        )

    return _build(root, root.name)
