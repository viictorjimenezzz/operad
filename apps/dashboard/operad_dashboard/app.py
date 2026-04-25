"""FastAPI app: serves the SPA shell, runs API, graph, and SSE stream."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from operad.runtime.cost import CostObserver
from operad.runtime.observers.base import registry as operad_registry
from operad.runtime.slots import registry as slot_registry

from .observer import WebDashboardObserver, serialize_event
from .routes import drift as drift_routes
from .routes import fitness as fitness_routes
from .routes import mutations as mutations_routes
from .routes import progress as progress_routes


_PKG_DIR = Path(__file__).resolve().parent
_WEB_DIR = _PKG_DIR / "web"
_WEB_INDEX = _WEB_DIR / "index.html"
_WEB_ASSETS = _WEB_DIR / "assets"

_SNAPSHOT_INTERVAL_SECONDS = 2.0
_MAX_EVENTS_PER_REQUEST = 500
_KNOWN_ENVELOPE_TYPES = {"agent_event", "algo_event", "slot_occupancy", "cost_update", "stats_update"}

def _dashboard_version() -> str:
    try:
        return version("operad-dashboard")
    except PackageNotFoundError:
        return "0.0.0"


def create_app(
    *,
    observer: WebDashboardObserver | None = None,
    cost_observer: CostObserver | None = None,
    auto_register: bool = True,
    langfuse_url: str | None = None,
) -> FastAPI:
    """Build a FastAPI app wired to a `WebDashboardObserver`.

    `auto_register=True` registers the observers with operad's process-wide
    registry so the dashboard sees in-process events without further setup.

    The web shell is the React SPA built from `apps/frontend/` and copied
    into `operad_dashboard/web/` (gitignored; populated by
    `make build-frontend`). When the SPA bundle isn't present (e.g.
    running tests without a frontend build), we fall back to a
    minimal HTML shell that still satisfies the legacy assertions.
    """
    app = FastAPI(title="operad-dashboard")
    obs = observer or WebDashboardObserver()
    cost = cost_observer or CostObserver()
    if auto_register:
        operad_registry.register(obs)
        operad_registry.register(cost)

    app.state.observer = obs
    app.state.cost_observer = cost
    app.state.langfuse_url = (langfuse_url or "").rstrip("/") or None

    # SPA assets first so /assets/X resolves without hitting the catch-all.
    if _WEB_ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_WEB_ASSETS)), name="assets")
    if _WEB_DIR.is_dir():
        app.mount(
            "/web",
            StaticFiles(directory=str(_WEB_DIR), html=False),
            name="web",
        )

    @app.get("/api/manifest")
    async def manifest() -> JSONResponse:
        mode = "production" if os.environ.get("OPERAD_ENV") == "production" else "development"
        return JSONResponse(
            {
                "mode": mode,
                "version": _dashboard_version(),
                "langfuseUrl": app.state.langfuse_url,
            }
        )

    @app.get("/runs")
    async def runs(include: str | None = None) -> JSONResponse:
        all_runs = obs.registry.list()
        if include != "synthetic":
            all_runs = [r for r in all_runs if not r.synthetic]
        return JSONResponse([r.summary() for r in all_runs])

    @app.get("/stats")
    async def stats() -> JSONResponse:
        s = obs.registry.global_stats()
        s["subscribers"] = obs.subscriber_count
        try:
            s["cost_totals"] = cost.totals()
        except Exception:
            s["cost_totals"] = {}
        return JSONResponse(s)

    @app.get("/evolution")
    async def evolution() -> JSONResponse:
        return JSONResponse({"generations": obs.registry.all_generations()})

    @app.get("/graph/{run_id}")
    async def graph(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        if info.mermaid is None:
            raise HTTPException(status_code=404, detail="no graph captured for run")
        return JSONResponse({"mermaid": info.mermaid})

    @app.get("/runs/{run_id}/summary")
    async def run_summary(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        totals = cost.totals().get(run_id, {})
        data = info.summary()
        data["cost"] = totals
        return JSONResponse(data)

    @app.get("/runs/{run_id}/children")
    async def run_children(run_id: str) -> JSONResponse:
        if obs.registry.get(run_id) is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        children = obs.registry.list_children(run_id)
        return JSONResponse([c.summary() for c in children])

    @app.get("/runs/{run_id}/parent")
    async def run_parent(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        if not info.synthetic or info.parent_run_id is None:
            raise HTTPException(status_code=404, detail="run is not synthetic")
        parent = obs.registry.get(info.parent_run_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="parent run not found")
        return JSONResponse(parent.summary())

    @app.get("/runs/{run_id}/tree")
    async def run_tree(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        children = obs.registry.list_children(run_id)
        return JSONResponse({"root": info.summary(), "children": [c.summary() for c in children]})

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str, limit: int = 200) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        limit = max(1, min(limit, _MAX_EVENTS_PER_REQUEST))
        events = list(info.events)[-limit:]
        return JSONResponse({"run_id": run_id, "events": events})

    @app.post("/_ingest")
    async def ingest(request: Request) -> JSONResponse:
        """HTTP-attach ingestion endpoint. Accepts a single envelope or a JSON array."""
        body = await request.json()
        envelopes: list[dict[str, Any]] = body if isinstance(body, list) else [body]
        for envelope in envelopes:
            env_type = envelope.get("type")
            if env_type == "graph_envelope":
                run_id = envelope.get("run_id") or ""
                mermaid = envelope.get("mermaid")
                if run_id and isinstance(mermaid, str):
                    info = obs.registry._ensure(run_id, time.time())
                    info.mermaid = mermaid
            elif env_type in _KNOWN_ENVELOPE_TYPES:
                await obs.broadcast(envelope)
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"unknown envelope type: {env_type!r}",
                )
        return JSONResponse({"ok": True})

    @app.get("/stream")
    async def stream(request: Request) -> EventSourceResponse:
        return EventSourceResponse(_event_stream(request, obs, cost))

    app.include_router(fitness_routes.router)
    app.include_router(mutations_routes.router)
    app.include_router(drift_routes.router)
    app.include_router(progress_routes.router)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(_render_shell())

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_catch_all(full_path: str) -> Response:
        # FastAPI tries explicit routes (registered above) before
        # falling here, so the catch-all only sees genuinely SPA URLs.
        # React Router renders 404 client-side for unknown routes.
        del full_path
        return HTMLResponse(_render_shell())

    return app


def _render_shell() -> str:
    """Return the SPA index.html if present; otherwise an informative stub.

    Tests run without a built frontend; the stub satisfies the
    `"operad" in r.text.lower()` assertion and explains what to do.
    """
    if _WEB_INDEX.is_file():
        return _WEB_INDEX.read_text(encoding="utf-8")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>operad - dashboard</title></head><body>"
        "<h1>operad</h1>"
        "<p>Frontend bundle not built. Run "
        "<code>make build-frontend</code> or "
        "<code>cd apps/frontend &amp;&amp; pnpm dev:dashboard</code>.</p>"
        "</body></html>"
    )


async def _event_stream(
    request: Request,
    obs: WebDashboardObserver,
    cost: CostObserver,
) -> AsyncIterator[dict[str, str]]:
    queue = obs.subscribe()
    snapshot_task = asyncio.create_task(_seed_snapshots(queue, obs, cost))
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": "message", "data": json.dumps(envelope, default=str)}
    finally:
        snapshot_task.cancel()
        obs.unsubscribe(queue)


async def _seed_snapshots(
    queue: asyncio.Queue[dict[str, Any]],
    obs: WebDashboardObserver,
    cost: CostObserver,
) -> None:
    """Periodically push slot occupancy, cost, and global stats snapshots."""
    while True:
        try:
            occupancy = [asdict(s) for s in slot_registry.occupancy()]
        except Exception:
            occupancy = []
        try:
            totals = cost.totals()
        except Exception:
            totals = {}
        try:
            stats_snapshot = obs.registry.global_stats()
        except Exception:
            stats_snapshot = {}
        for envelope in (
            {"type": "slot_occupancy", "snapshot": occupancy},
            {"type": "cost_update", "totals": totals},
            {"type": "stats_update", "stats": stats_snapshot},
        ):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(envelope)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        await asyncio.sleep(_SNAPSHOT_INTERVAL_SECONDS)


__all__ = ["create_app", "serialize_event"]
