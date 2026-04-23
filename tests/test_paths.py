"""Tests for `operad.utils.paths._resolve`."""

from __future__ import annotations

import pytest

from operad import Agent, BuildError
from operad.utils.paths import _resolve

from .conftest import A, B, FakeLeaf


class _Composite(Agent[A, B]):
    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=None, input=A, output=B)
        self.inner = FakeLeaf(config=cfg, input=A, output=B)

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return await self.inner(x)


def test_resolve_empty_path_returns_agent(cfg) -> None:
    a = _Composite(cfg)
    assert _resolve(a, "") is a


def test_resolve_single_segment(cfg) -> None:
    a = _Composite(cfg)
    assert _resolve(a, "inner") is a.inner


def test_resolve_missing_segment_raises(cfg) -> None:
    a = _Composite(cfg)
    with pytest.raises(BuildError) as exc:
        _resolve(a, "nope")
    assert exc.value.reason == "prompt_incomplete"
