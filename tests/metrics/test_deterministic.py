"""Tests for deterministic metrics."""

from __future__ import annotations
import asyncio
import pytest
from operad import Metric
from operad.metrics import ExactMatch, JsonValid, Latency
from ..conftest import A, B
from dataclasses import dataclass
from operad.metrics.base import MetricBase
from ..conftest import A
from operad.metrics import Contains
from operad.metrics import RegexMatch
from operad.metrics import Rouge1


# --- from test_metrics_deterministic.py ---
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


async def test_latency_score_zero_before_measure() -> None:
    m = Latency()
    assert await m.score(A(), A()) == 0.0


async def test_latency_score_is_useful_after_measure() -> None:
    m = Latency()

    async def sleeper() -> None:
        await asyncio.sleep(0.01)

    await m.measure(sleeper)
    s = await m.score(A(), A())
    assert 0.0 < s <= 1.0
    # Latest measurement is ~0.01s → 1 / 1.01 ≈ 0.99
    assert s > 0.9

# --- from test_metrics_base.py ---
pytestmark = pytest.mark.asyncio


@dataclass
class _ScoreOnly(MetricBase):
    name: str = "score_only"

    async def score(self, predicted, expected) -> float:
        return 1.0 if predicted == expected else 0.0


@dataclass
class _BatchOverride(MetricBase):
    name: str = "batch_override"

    async def score(self, predicted, expected) -> float:
        return 0.0

    async def score_batch(self, pairs) -> list[float]:
        return [42.0 for _ in pairs]


async def test_default_score_batch_loops_score() -> None:
    pairs = [(A(text="x"), A(text="x")), (A(text="y"), A(text="z"))]
    scores = await _ScoreOnly().score_batch(pairs)
    assert scores == [1.0, 0.0]


async def test_override_wins_over_default() -> None:
    pairs = [(A(text="x"), A(text="x")), (A(text="y"), A(text="y"))]
    scores = await _BatchOverride().score_batch(pairs)
    assert scores == [42.0, 42.0]

# --- from test_metrics_contains.py ---
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

# --- from test_metrics_regex.py ---
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

# --- from test_metrics_rouge.py ---
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
