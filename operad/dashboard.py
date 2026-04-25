"""Attach the running process's event stream to a separate dashboard server.

Use when the dashboard runs in its own terminal (``operad-dashboard
--port 7860``) and your agent runs in another Python process.

Transport reliability guarantee
---------------------------------
Events are serialised into an in-process ``asyncio.Queue`` (capacity 2 000).
A background drain task collects up to 50 items or waits 50 ms, then posts
a JSON batch via ``run_in_executor`` so urllib never blocks the event loop.
Failed POSTs are retried up to 3 times with 0.1 s / 0.2 s delays; after
that the batch is silently dropped so a down dashboard never stalls the
agent.

Shutdown flush
--------------
``atexit.register`` is called once, at ``attach()`` time.  When the
interpreter exits — including after the event loop has been torn down —
the atexit handler drains any remaining queue items synchronously via
urllib, honouring the same retry policy.  No events are lost as long as
the process exits cleanly after printing its last output line.

No new runtime dependencies are required; only stdlib.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import threading
import time
import urllib.request
from typing import Any

from .runtime.events import AlgorithmEvent
from .runtime.observers.base import AgentEvent, Event, registry

_DRAIN_BATCH_SIZE = 50
_DRAIN_INTERVAL_S = 0.05   # 50 ms
_RETRY_DELAYS = (0.1, 0.2)


def _serialize(event: Event) -> dict[str, Any]:
    if isinstance(event, AlgorithmEvent):
        return {
            "type": "algo_event",
            "run_id": event.run_id,
            "algorithm_path": event.algorithm_path,
            "kind": event.kind,
            "payload": event.payload,
            "started_at": event.started_at,
            "finished_at": event.finished_at,
            "metadata": event.metadata,
        }
    err = None
    if event.error is not None:
        err = {"type": type(event.error).__name__, "message": str(event.error)}
    out_dump = (
        event.output.model_dump(mode="json") if event.output is not None else None
    )
    in_dump = (
        event.input.model_dump(mode="json") if event.input is not None else None
    )
    return {
        "type": "agent_event",
        "run_id": event.run_id,
        "agent_path": event.agent_path,
        "kind": event.kind,
        "input": in_dump,
        "output": out_dump,
        "started_at": event.started_at,
        "finished_at": event.finished_at,
        "metadata": event.metadata,
        "error": err,
    }


def _post_batch_sync(url: str, batch: list[dict]) -> None:
    """POST a list of serialised event dicts to `url`.

    Retries up to 3 times with exponential delays. Silently drops after
    the third failure so a down dashboard never stalls the caller.
    """
    body = json.dumps(batch, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    for attempt in range(3):
        try:
            urllib.request.urlopen(req, timeout=2.0).close()
            return
        except Exception:
            if attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])


class _HttpForwardObserver:
    """HTTP-forwarding observer with reliable async transport.

    See module docstring for the full reliability contract.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._queue: asyncio.Queue | None = None
        self._drain_task: asyncio.Task | None = None
        self._lock = threading.Lock()  # guards lazy init

    # ------------------------------------------------------------------
    # Async path
    # ------------------------------------------------------------------

    def _ensure_drain_task(self) -> asyncio.Queue:
        with self._lock:
            if self._queue is None:
                self._queue = asyncio.Queue(maxsize=2000)
                self._drain_task = asyncio.get_event_loop().create_task(
                    self._drain_loop(), name="operad-dashboard-drain"
                )
        return self._queue  # type: ignore[return-value]

    async def on_event(self, event: Event) -> None:
        q = self._ensure_drain_task()
        try:
            q.put_nowait(_serialize(event))
        except asyncio.QueueFull:
            pass

    async def _drain_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            batch: list[dict] = []
            try:
                item = await self._queue.get()  # type: ignore[union-attr]
                batch.append(item)
                deadline = loop.time() + _DRAIN_INTERVAL_S
                while len(batch) < _DRAIN_BATCH_SIZE:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(
                            self._queue.get(), timeout=remaining  # type: ignore[union-attr]
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
            except asyncio.CancelledError:
                if self._queue is not None:
                    while not self._queue.empty():
                        try:
                            batch.append(self._queue.get_nowait())
                        except asyncio.QueueEmpty:
                            break
                if batch:
                    await loop.run_in_executor(
                        None, _post_batch_sync, self.url, batch
                    )
                return
            if batch:
                await loop.run_in_executor(
                    None, _post_batch_sync, self.url, batch
                )

    # ------------------------------------------------------------------
    # Synchronous flush (called by atexit — loop may already be closed)
    # ------------------------------------------------------------------

    def _flush_sync(self) -> None:
        """Drain remaining queue items synchronously at process exit."""
        if self._queue is None:
            return
        batch: list[dict] = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            _post_batch_sync(self.url, batch)

    # ------------------------------------------------------------------
    # Graph envelope
    # ------------------------------------------------------------------

    def post_graph(
        self, run_id: str, mermaid: str, agents: list[dict]
    ) -> None:
        """Queue a graph_envelope for delivery to the dashboard.

        Schema: ``{"type": "graph_envelope", "run_id": ...,
        "mermaid": ..., "agents": [{"path": ..., "input": ...,
        "output": ...}, ...]}``.

        Falls back to a synchronous POST if the drain task has not
        started yet (i.e. called before any events are emitted).
        """
        envelope: dict[str, Any] = {
            "type": "graph_envelope",
            "run_id": run_id,
            "mermaid": mermaid,
            "agents": agents,
        }
        if self._queue is None:
            _post_batch_sync(self.url, [envelope])
            return
        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            pass


def attach(host: str = "127.0.0.1", port: int = 7860) -> _HttpForwardObserver:
    """Register an HTTP-forwarding observer pointed at a dashboard process.

    Also registers an ``atexit`` handler that flushes any in-flight events
    synchronously before the interpreter shuts down.
    """
    obs = _HttpForwardObserver(f"http://{host}:{port}/_ingest")
    registry.register(obs)
    atexit.register(obs._flush_sync)
    return obs


__all__ = ["attach"]
