"""Tests for `replay`: re-score stored trace with new metrics, no network."""

from __future__ import annotations

import pytest

from operad.metrics import ExactMatch
from operad.runtime.trace import TraceObserver
from operad.runtime.observers import base as _obs
from operad.runtime.replay import replay

from tests.conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_replay_exact_match_returns_eval_report(cfg, assert_no_network) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 42}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await leaf(A(text="hi"))
    finally:
        _obs.registry.clear()
    t = obs.last()
    assert t is not None

    report = await replay(
        t,
        [ExactMatch()],
        expected=B(value=42),
        predicted_cls=B,
    )
    assert report.summary["exact_match"] == 1.0
    assert len(report.rows) == 1
    assert report.rows[0]["predicted"] == {"value": 42}


async def test_replay_mismatch_scores_zero(cfg, assert_no_network) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await leaf(A(text="hi"))
    finally:
        _obs.registry.clear()
    t = obs.last()
    assert t is not None

    report = await replay(t, [ExactMatch()], expected=B(value=99), predicted_cls=B)
    assert report.summary["exact_match"] == 0.0
