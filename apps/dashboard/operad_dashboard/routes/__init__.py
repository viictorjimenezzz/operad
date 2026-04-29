"""Per-run dashboard panels (fitness, mutations, drift, progress, run detail).

Each route module exports a FastAPI `APIRouter` mounted under
`/runs/{run_id}/...`. The `per_run_sse` helper below factors out the
history-replay-then-live-stream pattern shared by every panel's `.sse`
endpoint.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Callable, Iterable

from fastapi import HTTPException, Request

from ..observer import WebDashboardObserver
from ..opro_sessions import find_opro_session, merged_opro_events


_HEARTBEAT_TIMEOUT_SECONDS = 15.0


async def per_run_sse(
    request: Request,
    obs: WebDashboardObserver,
    run_id: str,
    *,
    event_type: str | None = "algo_event",
    kind: str | tuple[str, ...] | None = None,
    algorithm_path: str | tuple[str, ...] | None = None,
    transform: Callable[[dict], dict] | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Replay buffered envelopes for a run, then stream matching live events.

    Filters the shared subscribe/broadcast stream down to `run_id` plus
    the optional `kind` / `algorithm_path` criteria so each panel only
    sees events relevant to it. `transform` is applied after filtering —
    useful for panels that ship a derived shape (e.g. progress snapshots).
    """
    kinds = _as_tuple(kind)
    paths = _as_tuple(algorithm_path)

    queue = obs.subscribe()
    try:
        try:
            history = list(iter_run_events(request, obs, run_id))
        except HTTPException:
            # SSE generators cannot reliably surface HTTPException once the
            # stream machinery has started; treat unknown runs as empty
            # streams to avoid noisy exception-group logs.
            return
        for env in history:
            if _matches(env, event_type, kinds, paths):
                payload = transform(env) if transform else env
                yield {"event": "message", "data": json.dumps(payload, default=str)}
        while True:
            if await request.is_disconnected():
                return
            try:
                env = await asyncio.wait_for(
                    queue.get(), timeout=_HEARTBEAT_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            if env.get("run_id") != run_id:
                continue
            if not _matches(env, event_type, kinds, paths):
                continue
            payload = transform(env) if transform else env
            yield {"event": "message", "data": json.dumps(payload, default=str)}
    finally:
        obs.unsubscribe(queue)


def _as_tuple(value: str | tuple[str, ...] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _matches(
    env: dict,
    event_type: str | None,
    kinds: tuple[str, ...] | None,
    paths: tuple[str, ...] | None,
) -> bool:
    if event_type is not None and env.get("type") != event_type:
        return False
    if kinds is not None and env.get("kind") not in kinds:
        return False
    if paths is not None and env.get("algorithm_path") not in paths:
        return False
    return True


def iter_run_events(
    request: Request,
    obs: WebDashboardObserver,
    run_id: str,
    *,
    event_type: str | None = None,
    kind: str | tuple[str, ...] | None = None,
    algorithm_path: str | tuple[str, ...] | None = None,
) -> Iterable[dict[str, Any]]:
    session = find_opro_session(obs.registry, run_id)
    if session is not None:
        kinds = _as_tuple(kind)
        paths = _as_tuple(algorithm_path)
        return [
            env
            for env in merged_opro_events(session)
            if _matches(env, event_type, kinds, paths)
        ]

    info = obs.registry.get(run_id)
    if info is not None:
        return obs.registry.iter_events(
            run_id,
            event_type=event_type,
            kind=kind,
            algorithm_path=algorithm_path,
        )
    store = getattr(request.app.state, "archive_store", None)
    if store is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    events = record.get("events")
    if not isinstance(events, list):
        return []
    kinds = _as_tuple(kind)
    paths = _as_tuple(algorithm_path)
    return [
        env
        for env in events
        if isinstance(env, dict) and _matches(env, event_type, kinds, paths)
    ]


__all__ = ["iter_run_events", "per_run_sse"]
