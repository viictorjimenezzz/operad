"""Tests for the RegexMatch metric."""

from __future__ import annotations

import pytest

from operad import Metric, RegexMatch

from .conftest import A


pytestmark = pytest.mark.asyncio


async def test_regex_match_hits() -> None:
    m = RegexMatch(field="text", pattern=r"\d{3}")
    assert await m.score(A(text="call 555 now"), A()) == 1.0


async def test_regex_match_misses() -> None:
    m = RegexMatch(field="text", pattern=r"\d{3}")
    assert await m.score(A(text="no numbers"), A()) == 0.0


async def test_regex_match_caches_compiled_pattern() -> None:
    m = RegexMatch(field="text", pattern=r"foo")
    await m.score(A(text="foo"), A())
    assert m._compiled is not None


async def test_regex_match_is_runtime_checkable() -> None:
    assert isinstance(RegexMatch(field="text", pattern="x"), Metric)
