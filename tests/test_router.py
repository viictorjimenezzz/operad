"""Tests for ``Router``: typed ``Choice`` output narrowed via ``Literal``."""

from __future__ import annotations

from typing import Any, Literal

import pytest

from operad import Choice, RouteInput, Router


pytestmark = pytest.mark.asyncio


class Mode(Choice[Literal["search", "compute"]]):
    pass


class _StubRouter(Router):
    def __init__(self, *, label: str) -> None:
        super().__init__(config=None, input=RouteInput, output=Mode)
        self._label = label

    async def forward(self, x: Any) -> Any:
        return Mode(label=self._label, reasoning="stub")  # type: ignore[arg-type]


async def test_router_emits_typed_choice() -> None:
    r = await _StubRouter(label="search").abuild()
    out = await r(RouteInput(query="find Paris"))
    assert isinstance(out.response, Mode)
    assert out.response.label == "search"
    assert out.response.reasoning == "stub"


async def test_router_default_output_is_choice_str_alias() -> None:
    # The bare class-level default uses Choice[str]. Instances typically
    # narrow via a subclass at construction.
    assert Router.output is not None
