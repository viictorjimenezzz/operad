"""FastAPI app: serves the dashboard shell, runs API, graph, and SSE stream."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from operad.runtime.cost import CostObserver
from operad.runtime.observers.base import registry as operad_registry
from operad.runtime.slots import registry as slot_registry

from .observer import WebDashboardObserver, serialize_event
from .routes import drift as drift_routes
from .routes import fitness as fitness_routes
from .routes import mutations as mutations_routes
from .routes import progress as progress_routes
from .routes import run_detail as run_detail_routes


_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _PKG_DIR / "templates"
_STATIC_DIR = _PKG_DIR / "static"

_SNAPSHOT_INTERVAL_SECONDS = 2.0


def create_app(
    *,
    observer: WebDashboardObserver | None = None,
    cost_observer: CostObserver | None = None,
    auto_register: bool = True,
) -> FastAPI:
    """Build a FastAPI app wired to a `WebDashboardObserver`.

    `auto_register=True` registers the observers with operad's process-wide
    registry so the dashboard sees in-process events without further
    setup. Tests pass `auto_register=False` and feed events directly.
    """
    app = FastAPI(title="operad-dashboard")
    obs = observer or WebDashboardObserver()
    cost = cost_observer or CostObserver()
    if auto_register:
        operad_registry.register(obs)
        operad_registry.register(cost)

    app.state.observer = obs
    app.state.cost_observer = cost

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {})

    @app.get("/runs")
    async def runs() -> JSONResponse:
        items = [
            {
                "run_id": r.run_id,
                "started_at": r.started_at,
                "last_event_at": r.last_event_at,
                "state": r.state,
                "has_graph": r.mermaid is not None,
            }
            for r in obs.registry.list()
        ]
        return JSONResponse(items)

    @app.get("/graph/{run_id}")
    async def graph(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        if info.mermaid is None:
            raise HTTPException(status_code=404, detail="no graph captured for run")
        return JSONResponse({"mermaid": info.mermaid})

    @app.post("/_ingest")
    async def ingest(envelope: dict[str, Any]) -> JSONResponse:
        """HTTP-attach ingestion endpoint. Accepts a pre-serialised envelope."""
        await obs.broadcast(envelope)
        return JSONResponse({"ok": True})

    @app.get("/stream")
    async def stream(request: Request) -> EventSourceResponse:
        return EventSourceResponse(_event_stream(request, obs, cost))

    app.include_router(run_detail_routes.router)
    app.include_router(fitness_routes.router)
    app.include_router(mutations_routes.router)
    app.include_router(drift_routes.router)
    app.include_router(progress_routes.router)

    return app


async def _event_stream(
    request: Request,
    obs: WebDashboardObserver,
    cost: CostObserver,
) -> AsyncIterator[dict[str, str]]:
    queue = obs.subscribe()
    snapshot_task = asyncio.create_task(_seed_snapshots(queue, cost))
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Heartbeat keeps the SSE connection healthy through proxies.
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": "message", "data": json.dumps(envelope, default=str)}
    finally:
        snapshot_task.cancel()
        obs.unsubscribe(queue)


async def _seed_snapshots(
    queue: asyncio.Queue[dict[str, Any]], cost: CostObserver
) -> None:
    """Periodically push slot occupancy + cost snapshots into one subscriber's queue."""
    while True:
        try:
            occupancy = [asdict(s) for s in slot_registry.occupancy()]
        except Exception:
            occupancy = []
        try:
            totals = cost.totals()
        except Exception:
            totals = {}
        for envelope in (
            {"type": "slot_occupancy", "snapshot": occupancy},
            {"type": "cost_update", "totals": totals},
        ):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # Don't block snapshot emission if the subscriber is slow;
                # drop oldest and retry once.
                try:
                    queue.get_nowait()
                    queue.put_nowait(envelope)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        await asyncio.sleep(_SNAPSHOT_INTERVAL_SECONDS)


__all__ = ["create_app", "serialize_event"]
