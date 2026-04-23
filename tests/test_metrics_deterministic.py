"""Tests for deterministic metrics."""

from __future__ import annotations

import asyncio

import pytest

from operad import ExactMatch, JsonValid, Latency, Metric

from .conftest import A, B


pytestmark = pytest.mark.asyncio


async def test_exact_match_equal_inputs() -> None:
    m = ExactMatch()
    assert await m.score(A(text="hi"), A(text="hi")) == 1.0


async def test_exact_match_distinct_inputs() -> None:
    m = ExactMatch()
    assert await m.score(A(text="hi"), A(text="bye")) == 0.0


async def test_json_valid_passes_for_round_trippable_models() -> None:
    m = JsonValid()
    assert await m.score(B(value=7), B(value=7)) == 1.0


async def test_latency_measures_wall_clock() -> None:
    m = Latency()

    async def sleeper() -> None:
        await asyncio.sleep(0.01)

    score = await m.measure(sleeper)
    assert score < 0  # negated so higher-is-better
    assert m._measurements and m._measurements[0] >= 0.01


async def test_metric_protocol_is_runtime_checkable() -> None:
    assert isinstance(ExactMatch(), Metric)
    assert isinstance(JsonValid(), Metric)
    assert isinstance(Latency(), Metric)
