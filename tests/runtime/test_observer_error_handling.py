"""Tests for ObserverRegistry error surfacing (stream 1-2)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from operad.runtime.observers.base import ObserverRegistry
from operad.runtime.observers import AgentEvent

pytestmark = pytest.mark.asyncio


def _make_event() -> AgentEvent:
    return AgentEvent(
        run_id="test-run",
        agent_path="Test",
        kind="start",
        input=None,
        output=None,
        error=None,
        started_at=0.0,
        finished_at=None,
    )


class _Exploder:
    async def on_event(self, event: AgentEvent) -> None:
        raise RuntimeError("boom")


class _CancelExploder:
    async def on_event(self, event: AgentEvent) -> None:
        raise asyncio.CancelledError()


async def test_exploding_observer_pipeline_completes() -> None:
    reg = ObserverRegistry()
    exploder = _Exploder()
    reg.register(exploder)

    await reg.notify(_make_event())
    await reg.notify(_make_event())

    counts = reg.errors()
    assert counts[id(exploder)] == 2


async def test_first_failure_warns_subsequent_debugs(caplog: pytest.LogCaptureFixture) -> None:
    reg = ObserverRegistry()
    reg.register(_Exploder())

    with caplog.at_level(logging.DEBUG, logger="operad.observers"):
        await reg.notify(_make_event())
        await reg.notify(_make_event())
        await reg.notify(_make_event())

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(warnings) == 1
    assert len(debugs) == 2


async def test_strict_mode_reraises() -> None:
    reg = ObserverRegistry(strict=True)
    reg.register(_Exploder())

    with pytest.raises(RuntimeError, match="boom"):
        await reg.notify(_make_event())


async def test_cancelled_error_reraises() -> None:
    reg = ObserverRegistry()
    reg.register(_CancelExploder())

    with pytest.raises(asyncio.CancelledError):
        await reg.notify(_make_event())


async def test_errors_method_returns_counts() -> None:
    reg = ObserverRegistry()
    exploder = _Exploder()
    reg.register(exploder)

    await reg.notify(_make_event())
    await reg.notify(_make_event())

    counts = reg.errors()
    assert counts == {id(exploder): 2}
