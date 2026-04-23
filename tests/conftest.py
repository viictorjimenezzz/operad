"""Shared pytest fixtures and helpers for the operad test suite.

The tests never touch a real model; `FakeLeaf` overrides `forward` to
return a canned, correctly-typed `model_construct` of the declared output
so no network or provider credentials are required.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration


# --- Shared Pydantic schemas -------------------------------------------------


class A(BaseModel):
    text: str = ""


class B(BaseModel):
    value: int = 0


class C(BaseModel):
    label: str = ""


class D(BaseModel):
    payload: list[str] = []


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def cfg() -> Configuration:
    """A default, offline-safe Configuration for tests.

    Points at a llama.cpp-shaped endpoint but is never actually contacted
    because every test-only agent overrides `forward` (see `FakeLeaf`).
    """
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        temperature=0.0,
        max_tokens=16,
    )


# --- Helpers ---------------------------------------------------------------


class FakeLeaf(Agent[Any, Any]):
    """A leaf agent that never hits strands.

    Overrides `forward` to produce a valid instance of `self.output` via
    `model_construct`, optionally merging in a caller-provided payload.
    """

    def __init__(
        self,
        *,
        config: Configuration,
        input: type[BaseModel],
        output: type[BaseModel],
        task: str = "",
        canned: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config=config, input=input, output=output, task=task)
        self.canned: dict[str, Any] = dict(canned or {})

    async def forward(self, x: Any) -> Any:
        return self.output.model_construct(**self.canned)


class BrokenOutputLeaf(Agent[Any, Any]):
    """Leaf that intentionally returns the wrong type (used in tests)."""

    def __init__(
        self,
        *,
        config: Configuration,
        input: type[BaseModel],
        output: type[BaseModel],
        wrong: BaseModel,
    ) -> None:
        super().__init__(config=config, input=input, output=output)
        self.wrong = wrong

    async def forward(self, x: Any) -> Any:
        return self.wrong
