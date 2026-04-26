"""Pre-wired safety pipeline composite.

``SafetyGuard`` routes every input through a ``Context`` classifier and
then either forwards it to an inner agent (in-scope) or produces a
refusal response via ``Talker`` (out-of-scope).  Users no longer need to
wire the context-check/refusal fork by hand.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ...core.agent import Agent, _TRACER
from ...utils.errors import BuildError
from ...core.flow import Router
from .components import Context, Talker
from .schemas import (
    ContextInput,
    ContextOutput,
    SafeguardCategory,
    TalkerInput,
    TextResponse,
)


class _PassthroughLeaf(Agent[ContextInput, TextResponse]):
    """Default inner agent: returns the user message unchanged."""

    input = ContextInput
    output = TextResponse
    config = None  # never calls a model

    async def forward(self, x: ContextInput) -> TextResponse:  # type: ignore[override]
        return TextResponse(text=x.message)


class _BlockedRequest(BaseModel):
    """Envelope for blocked-branch handling."""

    original: ContextInput | None = None
    classification: ContextOutput | None = None


class _BlockedResponder(Agent[_BlockedRequest, Any]):
    """Out-of-scope branch: talker response or refusal_factory output."""

    input = _BlockedRequest
    output = TextResponse

    def __init__(
        self,
        *,
        talker: Talker,
        refusal_factory: Callable[[ContextInput, SafeguardCategory], Any] | None,
        output: type,
    ) -> None:
        super().__init__(config=None, input=_BlockedRequest, output=output)
        self.talker = talker
        self._refusal_factory = refusal_factory

    async def forward(self, x: _BlockedRequest) -> Any:  # type: ignore[override]
        if _TRACER.get() is not None:
            await self.talker(TalkerInput.model_construct())
            return self.output.model_construct()

        original = x.original or ContextInput.model_construct()
        classified = x.classification or ContextOutput.model_construct()

        if self._refusal_factory is not None:
            return self._refusal_factory(original, classified.category)

        talker_input = TalkerInput(
            context=original.context,
            exit_strategy=original.exit_strategy,
            recent_chat_history=original.recent_chat_history,
            safeguard_reason=f"{classified.category}: {classified.reason}",
            message=original.message,
        )
        return (await self.talker(talker_input)).response


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
        self.blocked = _BlockedResponder(
            talker=self.talker,
            refusal_factory=self._refusal_factory,
            output=output,
        )
        self.router = Router(
            router=self.classifier,
            branches={
                "in_scope": self.inner,
                "exit": self.blocked,
                "separate_domain": self.blocked,
                "mixed_scope": self.blocked,
                "dangerous_or_illegal": self.blocked,
                "sexual_disallowed": self.blocked,
                "distress_self_harm": self.blocked,
            },
            input=input,
            output=output,
            key_field="category",
            branch_input=self._branch_input,
        )

    def _branch_input(
        self,
        x: ContextInput,
        choice: BaseModel,
        branch: Agent[Any, Any],
    ) -> BaseModel:
        if branch is self.inner:
            return x
        return _BlockedRequest(
            original=x,
            classification=choice,  # type: ignore[arg-type]
        )

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
        return (await self.router(x)).response


__all__ = ["SafetyGuard"]
