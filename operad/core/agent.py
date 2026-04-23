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

from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any, ClassVar, Generic, Self, TYPE_CHECKING, TypeVar

import strands
from pydantic import BaseModel, ConfigDict

from ..runtime import acquire as _acquire_slot
from ..utils.errors import BuildError
from .config import Configuration
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
        return result.structured_output  # type: ignore[return-value,no-any-return]

    # --- framework entry point ----------------------------------------------
    async def invoke(self, x: In) -> Out:
        """Validate contract, then run `forward`.

        When a symbolic tracer is active (during `build()`), this method
        short-circuits into the tracer instead of running real logic.
        """
        tracer = _TRACER.get()
        if tracer is not None:
            return await tracer.record(self, x)  # type: ignore[return-value,no-any-return]

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

        return y

    async def __call__(self, x: In) -> Out:  # type: ignore[override]
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
