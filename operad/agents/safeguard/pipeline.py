"""Pre-wired safety pipeline composite.

``SafetyGuard`` routes every input through a ``Context`` classifier and
then either forwards it to an inner agent (in-scope) or produces a
refusal response via ``Talker`` (out-of-scope).  Users no longer need to
wire the context-check/refusal fork by hand.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

from ...core.agent import Agent, Out, _TRACER
from ...utils.errors import BuildError, SideEffectDuringTrace
from .components import Context, Talker
from .schemas import ContextInput, SafeguardCategory, TalkerInput, TextResponse


class _PassthroughLeaf(Agent[ContextInput, TextResponse]):
    """Default inner agent: returns the user message unchanged."""

    input = ContextInput
    output = TextResponse
    config = None  # never calls a model

    async def forward(self, x: ContextInput) -> TextResponse:  # type: ignore[override]
        return TextResponse(text=x.message)


class SafetyGuard(Agent[ContextInput, Any]):
    """Composite that routes inputs through a safeguard check.

    Builds an internal ``Context → {in_scope: inner, *: Talker}`` routing
    tree without requiring users to wire it manually.

    Args:
        context:         Pre-configured ``Context`` classifier leaf (stored as
                         ``self.classifier`` to avoid shadowing the prompt
                         ``context`` string attribute).
        talker:          Pre-configured ``Talker`` refusal leaf.
        inner:           The protected agent.  Defaults to a passthrough
                         that returns ``TextResponse(text=x.message)``.
        refusal_factory: Converts ``(ContextInput, SafeguardCategory)``
                         to ``Out`` for the refusal branch.  Required
                         when ``output`` is not ``TextResponse``.
        input:           Overrides the input type (must be ``ContextInput``
                         or a subclass).
        output:          The shared output type of ``inner`` and the
                         refusal branch.  Defaults to ``TextResponse``.
    """

    config = None  # composite: no direct model calls

    def __init__(
        self,
        *,
        context: Context,
        talker: Talker,
        inner: Agent[Any, Any] | None = None,
        refusal_factory: Callable[[ContextInput, SafeguardCategory], Any] | None = None,
        input: type = ContextInput,
        output: type = TextResponse,
    ) -> None:
        super().__init__(config=None, input=input, output=output)
        self.classifier = context
        self.inner: Agent[Any, Any] = inner if inner is not None else _PassthroughLeaf()
        self.talker = talker
        self._refusal_factory = refusal_factory

    def build(self, *args: Any, **kwargs: Any) -> "SafetyGuard":
        if self.output is not TextResponse and self._refusal_factory is None:
            raise BuildError(
                "refusal_factory_required",
                f"SafetyGuard has output={self.output.__name__!r} which is not "
                "TextResponse, but no refusal_factory was supplied.  "
                "Pass refusal_factory=lambda x, category: "
                f"{self.output.__name__}(...) to SafetyGuard.",
                agent="SafetyGuard",
            )
        return super().build(*args, **kwargs)

    async def abuild(self, *args: Any, **kwargs: Any) -> "SafetyGuard":  # type: ignore[override]
        if self.output is not TextResponse and self._refusal_factory is None:
            raise BuildError(
                "refusal_factory_required",
                f"SafetyGuard has output={self.output.__name__!r} which is not "
                "TextResponse, but no refusal_factory was supplied.  "
                "Pass refusal_factory=lambda x, category: "
                f"{self.output.__name__}(...) to SafetyGuard.",
                agent="SafetyGuard",
            )
        return await super().abuild(*args, **kwargs)

    async def forward(self, x: ContextInput) -> Any:  # type: ignore[override]
        tracer = _TRACER.get()
        if tracer is not None:
            warnings.warn(
                "SafetyGuard is tracing all branches; ensure they are "
                "side-effect-free.",
                SideEffectDuringTrace,
                stacklevel=3,
            )
            await self.classifier(x)
            await self.inner(x)
            await self.talker(TalkerInput.model_construct())
            return self.output.model_construct()

        ctx_out = (await self.classifier(x)).response

        if ctx_out.category == "in_scope":
            return (await self.inner(x)).response

        # refusal branch
        if self._refusal_factory is not None:
            return self._refusal_factory(x, ctx_out.category)

        talker_input = TalkerInput(
            context=x.context,
            exit_strategy=x.exit_strategy,
            recent_chat_history=x.recent_chat_history,
            safeguard_reason=f"{ctx_out.category}: {ctx_out.reason}",
            message=x.message,
        )
        return (await self.talker(talker_input)).response


__all__ = ["SafetyGuard"]
