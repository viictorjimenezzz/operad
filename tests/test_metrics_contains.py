"""Tests for the Contains metric."""

from __future__ import annotations

import pytest

from operad import Metric
from operad.metrics import Contains

from .conftest import A


pytestmark = pytest.mark.asyncio


async def test_contains_substring_match() -> None:
    m = Contains(field="text")
    assert await m.score(A(text="hello world"), A(text="hello")) == 1.0


async def test_contains_substring_mismatch() -> None:
    m = Contains(field="text")
    assert await m.score(A(text="hello world"), A(text="goodbye")) == 0.0


async def test_contains_identical_strings() -> None:
    m = Contains(field="text")
    assert await m.score(A(text="same"), A(text="same")) == 1.0


async def test_contains_empty_expected_always_matches() -> None:
    m = Contains(field="text")
    assert await m.score(A(text="anything"), A(text="")) == 1.0


async def test_contains_is_runtime_checkable() -> None:
    assert isinstance(Contains(field="text"), Metric)
