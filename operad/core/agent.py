"""The `Agent` base class.

A `operad.Agent` is a `strands.Agent` subclass with typed I/O,
PyTorch-style child tracking, and a `build()` step. Everything a user
would have put on a separate `Prompt` object — role, task, rules,
examples, typed input/output, config — lives directly on the Agent.
Class-level attribute defaults play the role of module hyperparameters;
instance attributes carry the live values, freely mutable before
`build()`.
"""

from __future__ import annotations

import copy
import sys
import time
import uuid
from collections.abc import Sequence
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Any, ClassVar, Generic, Self, TYPE_CHECKING, TypeVar

import strands
from pydantic import BaseModel, ConfigDict

from ..runtime import acquire as _acquire_slot
from ..utils.errors import BuildError
from .config import Configuration
from .output import (
    OperadOutput,
    _extract_usage,
    hash_configuration,
    hash_input,
    hash_output_schema,
    hash_prompt,
)
from .state import AgentState
from . import render

if TYPE_CHECKING:
    from .build import Tracer


In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Example(BaseModel, Generic[In, Out]):
    """Typed few-shot demonstration: one `(input, output)` pair."""

    input: In
    output: Out

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Per-task tracer. When set, `Agent.invoke` short-circuits into the tracer
# instead of validating and running `forward`. This is how `build()` performs
# symbolic tracing without touching an LLM.
_TRACER: ContextVar["Tracer | None"] = ContextVar("_TRACER", default=None)


# Per-call usage slot. Leaf `forward` writes token counts here from the
# strands result; the surrounding `invoke` reads them when building the
# `OperadOutput` envelope. Composites never write (no model call), so
# composite envelopes see `None` and leave usage fields unset.
_USAGE: ContextVar[dict[str, int] | None] = ContextVar("_USAGE", default=None)


try:
    _OPERAD_VERSION = _pkg_version("operad")
except PackageNotFoundError:  # editable install without dist-info
    _OPERAD_VERSION = "0.0.0+unknown"
_PYTHON_VERSION = sys.version.split()[0]


class Agent(strands.Agent, Generic[In, Out]):
    """Typed, composable agent.

    Subclass this to define either a leaf (use the default ``forward``,
    which delegates to ``strands.Agent.invoke_async`` with structured
    output) or a composite (override ``forward`` to route between
    sub-agents, which are auto-registered when assigned as attributes).

    Component subclasses declare their contract at the class level::

        class Reasoner(Agent[Question, Answer]):
            input = Question
            output = Answer
            role = "You are a careful reasoner."
            task = "Work through the problem step by step."
            rules = ("Show reasoning before the answer.",)

    Instantiate as ``Reasoner(config=cfg)``; any constructor kwarg
    overrides the matching class attribute.

    The call to ``strands.Agent.__init__`` is deferred to ``build()`` so
    that constructing an Agent never touches a provider and so that
    every attribute stays mutable beforehand.
    """

    # --- class-level defaults (override in subclasses) ----------------------
    input: ClassVar[type[BaseModel] | None] = None
    output: ClassVar[type[BaseModel] | None] = None
    role: ClassVar[str] = ""
    task: ClassVar[str] = ""
    rules: ClassVar[Sequence[str]] = ()
    examples: ClassVar[Sequence[Example[Any, Any]]] = ()

    # --- instance state (populated by __init__ / build) ---------------------
    config: Configuration | None
    _built: bool
    _children: dict[str, "Agent[Any, Any]"]
    _graph: Any  # populated by build(); typed as AgentGraph in operad.core.build

    def __init__(
        self,
        *,
        config: Configuration | None = None,
        role: str | None = None,
        task: str | None = None,
        rules: Sequence[str] | None = None,
        examples: Sequence[Example[In, Out]] | None = None,
        input: type[In] | None = None,
        output: type[Out] | None = None,
    ) -> None:
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_built", False)
        object.__setattr__(self, "_graph", None)

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
        return AgentState(
            class_name=type(self).__name__,
            role=self.role,
            task=self.task,
            rules=list(self.rules),
            examples=[e.model_dump(mode="json") for e in self.examples],
            config=(
                self.config.model_copy(deep=True) if self.config is not None else None
            ),
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

    def clone(self) -> Self:
        """Return a fresh, unbuilt deep copy of this agent.

        Preserves declared Agent state (role, task, rules, examples, config,
        input/output types) and the composite routing structure. Composite
        subclasses' extra attributes (e.g. `Pipeline._stages`,
        `Parallel._keys`/`_combine`) are deep-copied with cloned children
        substituted for their originals. Default-forward leaves skip the
        strands-owned internals written by `build()`; the caller rebuilds.

        Shared children (the same Agent attached under multiple attribute
        names) are cloned once and reattached under each name, preserving
        the parent's sharing topology.
        """
        new = type(self).__new__(type(self))
        object.__setattr__(new, "_children", {})
        object.__setattr__(new, "_built", False)
        object.__setattr__(new, "_graph", None)

        new.role = self.role
        new.task = self.task
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
        # (Pipeline._stages, Parallel._keys, Parallel._combine, etc.) that
        # references children. Deep-copy it with the clone memo so those
        # references point at the new clones. Default-forward leaves skip
        # this to avoid copying strands internals from `_init_strands`.
        if type(self).forward is not Agent.forward:
            _known = {
                "role", "task", "rules", "examples", "config", "input", "output",
                "_children", "_built", "_graph",
            }
            for name, value in self.__dict__.items():
                if name in _known or isinstance(value, Agent):
                    continue
                object.__setattr__(new, name, copy.deepcopy(value, memo))

        return new

    # --- message formatting (overridable) -----------------------------------
    def format_system_message(self) -> str:
        """Render the agent's static contract into a system-message string.

        Default: XML-tagged sections (``<role>``, ``<task>``, ``<rules>``,
        ``<examples>``, ``<output_schema>``). Override for a different
        wire format.
        """
        return render.render_system(self)

    def format_user_message(self, x: In) -> str:
        """Render a per-call input into the user-message string.

        Default: ``<input>`` block with one ``<field>`` per Pydantic
        field, carrying the field's ``description`` so the model
        understands each field's role.
        """
        return render.render_input(x)

    # --- default leaf forward ------------------------------------------------
    async def forward(self, x: In) -> Out:
        """Default leaf behavior: single Strands call with structured output.

        The system prompt was wired at ``build()`` time
        (see ``operad.core.build._init_strands``); here we only render
        the per-call user turn. Composite agents override this.
        """
        async with _acquire_slot(self.config):  # type: ignore[arg-type]
            result = await super().invoke_async(  # type: ignore[misc]
                self.format_user_message(x),
                structured_output_model=self.output,
            )
        _USAGE.set(_extract_usage(result))
        return result.structured_output  # type: ignore[return-value,no-any-return]

    # --- framework entry point ----------------------------------------------
    async def invoke(self, x: In) -> "OperadOutput[Out]":
        """Validate contract, run `forward`, return an `OperadOutput` envelope.

        When a symbolic tracer is active (during `build()`), this method
        short-circuits into the tracer instead of running real logic —
        the tracer returns the raw sentinel `Out`, not an envelope.
        """
        tracer = _TRACER.get()
        if tracer is not None:
            return await tracer.record(self, x)  # type: ignore[return-value,no-any-return]

        from ..runtime.observers import base as _obs

        parent_entry = _obs._PATH_STACK.get()
        if parent_entry is None:
            path = type(self).__name__
        else:
            parent_agent, parent_path = parent_entry
            attr = _attr_name_hint(parent_agent, self) or type(self).__name__
            path = f"{parent_path}.{attr}"

        run_id = _obs._RUN_ID.get() or uuid.uuid4().hex
        started_wall = time.time()
        started_mono = time.monotonic()
        tok_r = _obs._RUN_ID.set(run_id)
        tok_p = _obs._PATH_STACK.set((self, path))
        tok_u = _USAGE.set(None)
        try:
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "start", x, None, None, started_mono, None, {}
                )
            )

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

            y = await self.forward(x)

            if not isinstance(y, self.output):  # type: ignore[arg-type]
                raise BuildError(
                    "output_mismatch",
                    f"forward returned {type(y).__name__}, expected {self.output.__name__}",  # type: ignore[union-attr]
                    agent=type(self).__name__,
                )

            finished_mono = time.monotonic()
            envelope = self._wrap_output(
                y, x, run_id, path, started_wall, started_mono, finished_mono
            )

            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "end", x, y, None, started_mono, finished_mono, {}
                )
            )
            return envelope
        except BaseException as e:
            await _obs.registry.notify(
                _obs.AgentEvent(
                    run_id, path, "error", x, None, e, started_mono, time.monotonic(), {}
                )
            )
            raise
        finally:
            _obs._RUN_ID.reset(tok_r)
            _obs._PATH_STACK.reset(tok_p)
            _USAGE.reset(tok_u)

    def _wrap_output(
        self,
        y: "Out",
        x: "In",
        run_id: str,
        path: str,
        started_wall: float,
        started_mono: float,
        finished_mono: float,
    ) -> "OperadOutput[Out]":
        usage = _USAGE.get() or {}
        finished_wall = started_wall + (finished_mono - started_mono)
        envelope_cls = OperadOutput[self.output]  # type: ignore[valid-type]
        return envelope_cls.model_construct(
            response=y,
            hash_operad_version=_OPERAD_VERSION,
            hash_python_version=_PYTHON_VERSION,
            hash_model=(
                hash_configuration(self.config) if self.config is not None else "composite"
            ),
            hash_prompt=hash_prompt(
                getattr(self, "_rendered_system", "") or "",
                self.format_user_message(x),
            ),
            hash_graph=getattr(self, "_graph_hash", ""),
            hash_input=hash_input(x),
            hash_output_schema=hash_output_schema(self.output),  # type: ignore[arg-type]
            run_id=run_id,
            agent_path=path,
            started_at=started_wall,
            finished_at=finished_wall,
            latency_ms=(finished_mono - started_mono) * 1000.0,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cost_usd=None,
        )

    async def __call__(self, x: In) -> "OperadOutput[Out]":  # type: ignore[override]
        return await self.invoke(x)

    # --- build --------------------------------------------------------------
    def build(self) -> Self:
        """Symbolically trace the architecture and mark it ready for invoke.

        Synchronous entry point. Use `abuild()` when already inside a
        running event loop.
        """
        from .build import build_agent

        return build_agent(self)

    async def abuild(self) -> Self:
        """Async variant of `build()` for use inside a running event loop."""
        from .build import abuild_agent

        return await abuild_agent(self)


def _attr_name_hint(parent: "Agent[Any, Any]", child: "Agent[Any, Any]") -> str | None:
    for name, value in parent._children.items():
        if value is child:
            return name
    return None
