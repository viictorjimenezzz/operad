"""Attach the running process's event stream to a separate dashboard server.

Use when the dashboard runs in its own terminal (``operad-dashboard
--port 7860``) and your agent runs in another Python process.

Transport reliability guarantee
---------------------------------
Events are serialised into a thread-safe ``queue.Queue`` (capacity 2 000).
A daemon background thread drains up to 50 items at a time and posts them
as a JSON batch via blocking urllib. The queue and the worker thread are
**decoupled from asyncio** — they survive ``asyncio.run()`` teardown,
which is the failure mode that previously dropped most events.

Failed POSTs are retried up to 3 times with 0.1 s / 0.2 s delays; after
that the batch is silently dropped so a down dashboard never stalls the
agent.

Shutdown flush
--------------
``atexit.register`` is wired in ``attach()``. When the interpreter exits,
the atexit handler tells the drain thread to stop, joins it (so any
in-flight POSTs complete), then drains any residual items synchronously
through the same retry-bound POST helper. No events are lost as long as
the process exits cleanly after printing its last output line.

No new runtime dependencies are required; only stdlib.
"""

from __future__ import annotations

import atexit
import json
import queue
import threading
import time
import urllib.request
from typing import Any

from .runtime.events import AlgorithmEvent
from .runtime.observers.base import AgentEvent, Event, registry

_QUEUE_CAPACITY = 2000
_DRAIN_BATCH_SIZE = 50
_DRAIN_GET_TIMEOUT_S = 0.05
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
    """HTTP-forwarding observer with reliable thread-based transport.

    See module docstring for the full reliability contract.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=_QUEUE_CAPACITY
        )
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._drain_loop,
            name="operad-dashboard-drain",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Producer side — called from the agent's event loop.
    # ------------------------------------------------------------------

    async def on_event(self, event: Event) -> None:
        # `queue.Queue.put_nowait` is thread-safe; no await needed. We
        # serialise here (rather than in the worker) so that mutations
        # to event-payload objects after enqueue do not race the POST.
        try:
            self._queue.put_nowait(_serialize(event))
        except queue.Full:
            pass

    def post_graph(
        self, run_id: str, mermaid: str, agents: list[dict]
    ) -> None:
        """Queue a graph_envelope for delivery to the dashboard.

        Schema: ``{"type": "graph_envelope", "run_id": ...,
        "mermaid": ..., "agents": [...]}``.
        """
        envelope: dict[str, Any] = {
            "type": "graph_envelope",
            "run_id": run_id,
            "mermaid": mermaid,
            "agents": agents,
        }
        try:
            self._queue.put_nowait(envelope)
        except queue.Full:
            pass

    # ------------------------------------------------------------------
    # Consumer side — runs on the daemon thread.
    # ------------------------------------------------------------------

    def _drain_loop(self) -> None:
        while not self._stop.is_set():
            try:
                first = self._queue.get(timeout=_DRAIN_GET_TIMEOUT_S)
            except queue.Empty:
                continue
            batch: list[dict] = [first]
            for _ in range(_DRAIN_BATCH_SIZE - 1):
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            _post_batch_sync(self.url, batch)

    # ------------------------------------------------------------------
    # Shutdown — invoked by atexit.
    # ------------------------------------------------------------------

    def _flush_sync(self) -> None:
        """Stop the worker thread and POST any remaining queued items.

        Idempotent. Safe to call from atexit even after the asyncio
        event loop has been torn down.
        """
        self._stop.set()
        # Wait for the worker to finish its current iteration. With a
        # 50ms get timeout it will return promptly.
        self._thread.join(timeout=2.0)
        residual: list[dict] = []
        while True:
            try:
                residual.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if residual:
            _post_batch_sync(self.url, residual)


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
