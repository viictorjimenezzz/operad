"""WebDashboardObserver: ingest operad events, fan out to SSE subscribers."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import AgentEvent, Event

from .runs import RunRegistry


_QUEUE_MAXSIZE = 1024


def _dump_payload(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, BaseModel):
        try:
            return x.model_dump(mode="json")
        except Exception:
            return repr(x)
    return repr(x)


def serialize_event(event: Event) -> dict[str, Any]:
    """Convert an operad Event into a JSON-safe envelope dict for SSE."""
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
    # AgentEvent
    error_dict: dict[str, str] | None = None
    if event.error is not None:
        error_dict = {
            "type": type(event.error).__name__,
            "message": str(event.error),
        }
    metadata = _safe_metadata(event.metadata)
    return {
        "type": "agent_event",
        "run_id": event.run_id,
        "agent_path": event.agent_path,
        "kind": event.kind,
        "input": _dump_payload(event.input),
        "output": _dump_payload(event.output),
        "started_at": event.started_at,
        "finished_at": event.finished_at,
        "metadata": metadata,
        "error": error_dict,
    }


def _safe_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Strip the (potentially large) graph dict from streamed metadata.

    The graph is cached separately by RunRegistry and served at
    /graph/{run_id}; sending it on every event would saturate the SSE
    channel.
    """
    if "graph" not in meta:
        return meta
    out = dict(meta)
    out["graph"] = "<cached at /graph/{run_id}>"
    return out


class WebDashboardObserver:
    """Operad Observer that broadcasts events to per-subscriber asyncio queues."""

    def __init__(
        self,
        registry: RunRegistry | None = None,
        *,
        events_per_run: int | None = None,
    ) -> None:
        if registry is not None:
            self.registry = registry
        elif events_per_run is not None:
            self.registry = RunRegistry(events_per_run=events_per_run)
        else:
            self.registry = RunRegistry()
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def on_event(self, event: Event) -> None:
        envelope = serialize_event(event)
        self.registry.record_envelope(envelope)
        await self.broadcast(envelope, record=False)

    async def broadcast(
        self, envelope: dict[str, Any], *, record: bool = True
    ) -> None:
        """Push one envelope to every subscriber; drop oldest on overflow.

        `record=True` (the default, used by the HTTP /_ingest and replay
        paths) also feeds the envelope into the run registry so summaries
        stay consistent across in-process and HTTP-attached producers.
        Set to False when the caller already recorded the envelope.
        """
        if record:
            self.registry.record_envelope(envelope)
        for q in list(self._subscribers):
            _put_drop_oldest(q, envelope)


def _put_drop_oldest(q: asyncio.Queue[dict[str, Any]], item: dict[str, Any]) -> None:
    while True:
        try:
            q.put_nowait(item)
            return
        except asyncio.QueueFull:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                return
