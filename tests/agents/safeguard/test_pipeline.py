"""Offline tests for SafetyGuard composite."""

from __future__ import annotations

import warnings
from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, BuildError, Configuration
from operad.agents.safeguard import Context, SafetyGuard, Talker
from operad.agents.safeguard.schemas import (
    ContextInput,
    ContextOutput,
    SafeguardCategory,
    TalkerInput,
    TextResponse,
)
from operad.utils.errors import SideEffectDuringTrace


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fake leaves
# ---------------------------------------------------------------------------

class FakeContext(Agent[ContextInput, ContextOutput]):
    """Context leaf that returns a canned classification."""

    def __init__(self, *, config: Configuration, category: SafeguardCategory = "in_scope") -> None:
        super().__init__(config=config, input=ContextInput, output=ContextOutput)
        self._category = category

    async def forward(self, x: ContextInput) -> ContextOutput:  # type: ignore[override]
        continue_field = "yes" if self._category == "in_scope" else (
            "exit" if self._category == "exit" else "no"
        )
        return ContextOutput(
            reason="canned",
            continue_field=continue_field,
            category=self._category,
        )


class FakeTalker(Agent[TalkerInput, TextResponse]):
    """Talker leaf that returns a canned refusal text."""

    def __init__(self, *, config: Configuration, text: str = "refused") -> None:
        super().__init__(config=config, input=TalkerInput, output=TextResponse)
        self._text = text

    async def forward(self, x: TalkerInput) -> TextResponse:  # type: ignore[override]
        return TextResponse(text=self._text)


class MyOutput(BaseModel):
    message: str = ""


class FakeInner(Agent[ContextInput, MyOutput]):
    def __init__(self, *, config: Configuration) -> None:
        super().__init__(config=config, input=ContextInput, output=MyOutput)

    async def forward(self, x: ContextInput) -> MyOutput:  # type: ignore[override]
        return MyOutput(message=f"inner:{x.message}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_in_scope_passthrough(cfg: Configuration) -> None:
    """In-scope message is forwarded to the default passthrough inner."""
    guard = SafetyGuard(
        context=FakeContext(config=cfg, category="in_scope"),
        talker=FakeTalker(config=cfg),
    )
    await guard.abuild()

    result = await guard(ContextInput(message="hello"))
    assert isinstance(result.response, TextResponse)
    assert result.response.text == "hello"


async def test_out_of_scope_refusal(cfg: Configuration) -> None:
    """Out-of-scope message triggers Talker and returns its text."""
    guard = SafetyGuard(
        context=FakeContext(config=cfg, category="separate_domain"),
        talker=FakeTalker(config=cfg, text="sorry, out of scope"),
    )
    await guard.abuild()

    result = await guard(ContextInput(message="what is the weather?"))
    assert isinstance(result.response, TextResponse)
    assert result.response.text == "sorry, out of scope"


async def test_custom_inner_agent(cfg: Configuration) -> None:
    """In-scope message is forwarded to the user-supplied inner agent."""
    guard = SafetyGuard(
        context=FakeContext(config=cfg, category="in_scope"),
        talker=FakeTalker(config=cfg),
        inner=FakeInner(config=cfg),
        output=MyOutput,
        refusal_factory=lambda x, cat: MyOutput(message="blocked"),
    )
    await guard.abuild()

    result = await guard(ContextInput(message="ping"))
    assert isinstance(result.response, MyOutput)
    assert result.response.message == "inner:ping"


async def test_refusal_factory_on_block(cfg: Configuration) -> None:
    """When a refusal_factory is set, it is called for blocked messages and Talker is skipped."""
    talker_called = False

    class TrackingTalker(Agent[TalkerInput, TextResponse]):
        def __init__(self) -> None:
            super().__init__(config=cfg, input=TalkerInput, output=TextResponse)

        async def forward(self, x: TalkerInput) -> TextResponse:  # type: ignore[override]
            nonlocal talker_called
            talker_called = True
            return TextResponse(text="should not appear")

    factory_calls: list[SafeguardCategory] = []

    def factory(x: ContextInput, cat: SafeguardCategory) -> MyOutput:
        factory_calls.append(cat)
        return MyOutput(message=f"factory:{cat}")

    guard = SafetyGuard(
        context=FakeContext(config=cfg, category="dangerous_or_illegal"),
        talker=TrackingTalker(),
        inner=FakeInner(config=cfg),
        output=MyOutput,
        refusal_factory=factory,
    )
    await guard.abuild()

    result = await guard(ContextInput(message="do something bad"))
    assert isinstance(result.response, MyOutput)
    assert result.response.message == "factory:dangerous_or_illegal"
    assert factory_calls == ["dangerous_or_illegal"]
    assert not talker_called


async def test_build_error_without_refusal_factory(cfg: Configuration) -> None:
    """build() raises BuildError when output != TextResponse and no refusal_factory."""
    guard = SafetyGuard(
        context=FakeContext(config=cfg),
        talker=FakeTalker(config=cfg),
        inner=FakeInner(config=cfg),
        output=MyOutput,
        # no refusal_factory
    )
    with pytest.raises(BuildError) as exc_info:
        await guard.abuild()

    assert exc_info.value.reason == "refusal_factory_required"
    assert "SafetyGuard" in exc_info.value.agent
