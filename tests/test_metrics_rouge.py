"""Tests for Rouge1 (unigram-overlap F1)."""

from __future__ import annotations

import pytest

from operad import Metric, Rouge1

from .conftest import A


pytestmark = pytest.mark.asyncio


async def test_rouge1_exact_match() -> None:
    m = Rouge1(field="text")
    assert await m.score(A(text="the cat sat"), A(text="the cat sat")) == 1.0


async def test_rouge1_disjoint() -> None:
    m = Rouge1(field="text")
    assert await m.score(A(text="alpha beta"), A(text="gamma delta")) == 0.0


async def test_rouge1_partial_overlap() -> None:
    m = Rouge1(field="text")
    # pred unigrams: {a, b, c}, ref: {b, c, d}, overlap=2
    # P = 2/3, R = 2/3, F1 = 2/3
    s = await m.score(A(text="a b c"), A(text="b c d"))
    assert abs(s - 2 / 3) < 1e-9


async def test_rouge1_empty_side_returns_zero() -> None:
    m = Rouge1(field="text")
    assert await m.score(A(text=""), A(text="hi")) == 0.0
    assert await m.score(A(text="hi"), A(text="")) == 0.0


async def test_rouge1_is_runtime_checkable() -> None:
    assert isinstance(Rouge1(field="text"), Metric)
