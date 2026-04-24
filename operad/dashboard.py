"""Attach the running process's event stream to a separate dashboard server.

Use when the dashboard runs in its own terminal (`operad-dashboard
--port 7860`) and your agent runs in another Python process. POSTs each
serialised event to the dashboard's ``/_ingest`` endpoint via
``urllib`` (no extra runtime dep).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from .runtime.events import AlgorithmEvent
from .runtime.observers.base import AgentEvent, Event, registry


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


class _HttpForwardObserver:
    def __init__(self, url: str) -> None:
        self.url = url

    async def on_event(self, event: Event) -> None:
        body = json.dumps(_serialize(event), default=str).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=2.0).close()
        except Exception:
            # Dashboard offline; never break the agent run.
            pass


def attach(host: str = "127.0.0.1", port: int = 7860) -> _HttpForwardObserver:
    """Register an HTTP-forwarding observer pointed at a dashboard process."""
    obs = _HttpForwardObserver(f"http://{host}:{port}/_ingest")
    registry.register(obs)
    return obs


__all__ = ["attach"]
