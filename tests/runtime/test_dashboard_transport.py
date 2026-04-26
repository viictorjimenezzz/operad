"""Tests for operad/dashboard.py transport reliability (stream 1-1).

The transport is thread-decoupled from asyncio: a daemon worker drains
a stdlib ``queue.Queue`` and POSTs batches via blocking urllib. The
worker survives event-loop teardown so atexit can flush residual items
without needing a live loop.
"""

from __future__ import annotations

import asyncio
import queue
import time
from typing import Any

import pytest

from operad.dashboard import _HttpForwardObserver
from operad.runtime.observers.base import (
    AgentEvent,
    _ALGO_RUN_ID,
    _enter_algorithm_run,
    registry as obs_registry,
)

from .._helpers.fake_leaf import A, B, FakeLeaf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Collector:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def on_event(self, event: Any) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


# ---------------------------------------------------------------------------
# Test 1: atexit flush drains residual items synchronously after the worker
#         has been stopped.
# ---------------------------------------------------------------------------


def test_atexit_flush_posts_queued_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Items still in the queue when _flush_sync is called are posted."""
    posted: list[list] = []

    def fake_post(url: str, batch: list) -> None:
        posted.append(list(batch))

    monkeypatch.setattr("operad.dashboard._post_batch_sync", fake_post)

    obs = _HttpForwardObserver("http://127.0.0.1:7860/_ingest")
    # Stop the worker first so it does not race the test on draining.
    obs._stop.set()
    obs._thread.join(timeout=2.0)
    for i in range(5):
        obs._queue.put_nowait({"type": "agent_event", "seq": i})

    obs._flush_sync()

    # Either one batch (residual flush) or zero — depending on whether the
    # worker beat _flush_sync to anything. Regardless, all 5 items must
    # have made it to fake_post in total.
    total = sum(len(b) for b in posted)
    assert total == 5


# ---------------------------------------------------------------------------
# Test 2: the worker thread batches events and delivers them.
# ---------------------------------------------------------------------------


def test_drain_thread_batches_and_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Events queued via on_event are collected and delivered via _post_batch_sync."""
    posted: list[list] = []

    def fake_post(url: str, batch: list) -> None:
        posted.append(list(batch))

    monkeypatch.setattr("operad.dashboard._post_batch_sync", fake_post)

    obs = _HttpForwardObserver("http://127.0.0.1:7860/_ingest")
    try:
        # `on_event` is async but its body is sync (queue.put_nowait). Drive
        # it from a fresh event loop so the test stays sync-friendly.
        loop = asyncio.new_event_loop()
        try:
            for _ in range(3):
                loop.run_until_complete(
                    obs.on_event(
                        AgentEvent(
                            run_id="r1",
                            agent_path="L",
                            kind="start",
                            input=None,
                            output=None,
                            error=None,
                            started_at=1.0,
                            finished_at=None,
                        )
                    )
                )
        finally:
            loop.close()
        # Allow the worker to wake up (50 ms get-timeout) and drain.
        deadline = time.monotonic() + 1.0
        while sum(len(b) for b in posted) < 3 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert sum(len(b) for b in posted) == 3
    finally:
        obs._stop.set()
        obs._thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Test 3: parent_run_id propagation inside an algorithm scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parent_run_id_set_inside_algorithm_scope(cfg) -> None:
    """AgentEvents emitted inside _enter_algorithm_run carry parent_run_id."""
    col = _Collector()
    obs_registry.register(col)

    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    await leaf.abuild()

    algo_rid: str
    with _enter_algorithm_run() as algo_rid:
        await leaf(A())

    agent_events = [e for e in col.events if isinstance(e, AgentEvent)]
    assert agent_events, "expected at least one AgentEvent"
    # All agent events inside the algorithm scope must carry parent_run_id.
    for e in agent_events:
        assert e.metadata.get("parent_run_id") == algo_rid, (
            f"expected parent_run_id={algo_rid!r}, got metadata={e.metadata}"
        )


# ---------------------------------------------------------------------------
# Test 4: _ALGO_RUN_ID is reset after _enter_algorithm_run exits
# ---------------------------------------------------------------------------


def test_algo_run_id_cleaned_up_after_scope() -> None:
    """_ALGO_RUN_ID must be None outside an algorithm scope."""
    assert _ALGO_RUN_ID.get() is None
    with _enter_algorithm_run():
        inside = _ALGO_RUN_ID.get()
        assert inside is not None
    assert _ALGO_RUN_ID.get() is None
