"""Shared pytest fixtures and helpers for the operad test suite.

The tests never touch a real model; `FakeLeaf` overrides `forward` to
return a canned, correctly-typed `model_construct` of the declared output
so no network or provider credentials are required.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

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


@pytest.fixture
def cassette(request: pytest.FixtureRequest) -> Iterator[None]:
    """Record/replay LLM calls for this test via a JSONL cassette.

    Default mode is ``replay`` (missing keys raise ``CassetteMiss``).
    Set ``OPERAD_CASSETTE=record`` against a real backend to refresh the
    file at ``<testfile_dir>/cassettes/<test_name>.jsonl``.
    """
    from operad.testing.cassette import cassette_context

    mode = os.environ.get("OPERAD_CASSETTE", "replay")
    if mode not in ("record", "replay"):
        raise ValueError(
            f"OPERAD_CASSETTE must be 'record' or 'replay', got {mode!r}"
        )
    path = (
        Path(request.fspath).parent / "cassettes" / f"{request.node.name}.jsonl"
    )
    with cassette_context(path, mode=mode):  # type: ignore[arg-type]
        yield


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


@pytest.fixture
def assert_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any outbound socket or HTTP send raise.

    Attach in tests that claim zero-cost replay. The fixture patches
    both ``socket.socket.connect`` and ``httpx.AsyncClient.send`` (if
    httpx is installed) for the duration of the test.
    """
    import socket

    def _blocked_connect(*a: Any, **k: Any) -> None:
        raise AssertionError("network call blocked by assert_no_network fixture")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    try:
        import httpx

        async def _blocked_send(*a: Any, **k: Any) -> None:
            raise AssertionError("network call blocked by assert_no_network fixture")

        monkeypatch.setattr(httpx.AsyncClient, "send", _blocked_send)
    except ImportError:
        pass


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
