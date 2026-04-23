"""Tests for the CostTracker (stub-event-driven accumulator)."""

from __future__ import annotations

import pytest

from operad import CostTracker
from operad.metrics.cost import _CostEvent


pytestmark = pytest.mark.asyncio


async def test_cost_tracker_accumulates_per_run() -> None:
    tracker = CostTracker()
    await tracker.on_event(
        _CostEvent(
            run_id="r1",
            backend="anthropic",
            model="claude-haiku-4-5",
            prompt_text="a" * 400,          # ~100 prompt tokens
            completion_text="b" * 200,       # ~50 completion tokens
        )
    )
    await tracker.on_event(
        _CostEvent(
            run_id="r1",
            backend="anthropic",
            model="claude-haiku-4-5",
            prompt_text="c" * 40,            # ~10
            completion_text="d" * 40,        # ~10
        )
    )
    await tracker.on_event(
        _CostEvent(
            run_id="r2",
            backend="llamacpp",
            model="default",
            prompt_text="free " * 20,
        )
    )

    totals = tracker.totals()
    assert set(totals.keys()) == {"r1", "r2"}
    assert totals["r1"]["prompt_tokens"] == 110
    assert totals["r1"]["completion_tokens"] == 60
    # claude-haiku: 0.001/1k prompt + 0.005/1k completion
    expected = (110 * 0.001 + 60 * 0.005) / 1000.0
    assert abs(totals["r1"]["cost_usd"] - expected) < 1e-12
    assert totals["r2"]["cost_usd"] == 0.0


async def test_cost_tracker_unknown_model_is_free() -> None:
    tracker = CostTracker()
    await tracker.on_event(
        _CostEvent(
            run_id="x",
            backend="nobody",
            model="whoknows",
            prompt_text="hello world",
        )
    )
    assert tracker.totals()["x"]["cost_usd"] == 0.0


async def test_cost_tracker_empty_before_events() -> None:
    assert CostTracker().totals() == {}
