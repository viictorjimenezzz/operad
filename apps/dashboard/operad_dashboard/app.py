"""FastAPI app: serves the SPA shell, runs API, graph, and SSE stream."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from operad.metrics.cost import CostObserver
from operad.runtime.observers.base import registry as operad_registry
from operad.runtime.slots import registry as slot_registry

from .benchmark_store import BenchmarkStore
from .observer import WebDashboardObserver, serialize_event
from .persistence import SQLiteRunArchive
from .routes import archive as archive_routes
from .routes import benchmarks as benchmark_routes
from .routes import checkpoints as checkpoints_routes
from .routes import cassettes as cassettes_routes
from .routes import debate as debate_routes
from .routes import drift as drift_routes
from .routes import fitness as fitness_routes
from .routes import gradients as gradients_routes
from .routes import groups as groups_routes
from .routes import iterations as iterations_routes
from .routes import mutations as mutations_routes
from .routes import progress as progress_routes
from .routes import sweep as sweep_routes
from .routes import traceback as traceback_routes
from . import agent_routes

ExperimentResolver = Callable[[str, str], Any | None]

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


def _repo_root() -> Path:
    return _PKG_DIR.parents[2]


def _cassette_stale(path_value: str | None) -> bool:
    if not isinstance(path_value, str) or not path_value.strip():
        return False
    raw_path = Path(path_value).expanduser()
    path = raw_path if raw_path.is_absolute() else (_repo_root() / raw_path)
    try:
        cassette_mtime = path.stat().st_mtime
    except OSError:
        return False
    source_root = _repo_root() / "operad"
    if not source_root.is_dir():
        return False
    for source in source_root.rglob("*.py"):
        try:
            if source.stat().st_mtime > cassette_mtime:
                return True
        except OSError:
            continue
    return False


def create_app(
    *,
    observer: WebDashboardObserver | None = None,
    cost_observer: CostObserver | None = None,
    auto_register: bool = True,
    langfuse_url: str | None = None,
    data_dir: Path | str | None = None,
    benchmark_dir: str = "./.benchmarks/",
    allow_experiment: bool = False,
    experiment_resolver: ExperimentResolver | None = None,
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
    archive_store = (
        SQLiteRunArchive(data_dir) if data_dir is not None else None
    )
    obs = observer or WebDashboardObserver(persistence=archive_store)
    if observer is not None and archive_store is not None:
        obs.persistence = archive_store
    cost = cost_observer or CostObserver()
    if auto_register:
        operad_registry.register(obs)
        operad_registry.register(cost)

    app.state.observer = obs
    app.state.cost_observer = cost
    app.state.langfuse_url = (langfuse_url or "").rstrip("/") or None
    app.state.archive_store = archive_store
    app.state.benchmark_store = BenchmarkStore()
    app.state.benchmark_dir = benchmark_dir
    app.state.allow_experiment = bool(allow_experiment)
    app.state.experiment_resolver = experiment_resolver
    experiment_root = Path(data_dir) if data_dir is not None else Path("./.dashboard-data")
    app.state.experiment_log_path = experiment_root / "experiments.ndjson"

    @app.on_event("startup")
    async def _load_benchmarks_from_dir() -> None:
        bench_dir = Path(str(app.state.benchmark_dir))
        if not bench_dir.is_dir():
            return
        store: BenchmarkStore = app.state.benchmark_store
        for path in sorted(bench_dir.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                store.ingest(payload)
            except Exception:
                continue

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
        cassette_path = os.environ.get("OPERAD_CASSETTE_PATH")
        return JSONResponse(
            {
                "mode": mode,
                "version": _dashboard_version(),
                "langfuseUrl": app.state.langfuse_url,
                "allowExperiment": app.state.allow_experiment,
                "cassetteMode": bool(os.environ.get("OPERAD_CASSETTE")),
                "cassettePath": cassette_path,
                "cassetteStale": _cassette_stale(cassette_path),
                "tracePath": os.environ.get("OPERAD_TRACE"),
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
        mermaid = info.mermaid if info is not None else None
        if mermaid is None and archive_store is not None:
            mermaid = archive_store.get_mermaid(run_id)
        if mermaid is None:
            if info is None:
                raise HTTPException(status_code=404, detail="unknown run_id")
            raise HTTPException(status_code=404, detail="no graph captured for run")
        return JSONResponse({"mermaid": mermaid})

    @app.get("/runs/{run_id}/summary")
    async def run_summary(run_id: str) -> JSONResponse:
        info = obs.registry.get(run_id)
        if info is not None:
            data = info.summary()
        elif archive_store is not None:
            archived = archive_store.get_run(run_id)
            if archived is None:
                raise HTTPException(status_code=404, detail="unknown run_id")
            summary = archived.get("summary")
            if not isinstance(summary, dict):
                raise HTTPException(status_code=500, detail="corrupt archive record")
            data = summary
        else:
            raise HTTPException(status_code=404, detail="unknown run_id")
        totals = cost.totals().get(run_id, {})
        data["cost"] = totals
        return JSONResponse(data)

    @app.patch("/api/runs/{run_id}/notes")
    async def update_notes(request: Request, run_id: str) -> JSONResponse:
        body = await request.json()
        markdown = str(body.get("markdown") or "")
        info = obs.registry.get(run_id)
        if info is not None:
            info.notes_markdown = markdown
        if archive_store is not None:
            if info is not None:
                archive_store.upsert_snapshot(info)
            archive_store.set_notes(run_id, markdown)
        return JSONResponse(
            {
                "run_id": run_id,
                "notes_markdown": markdown,
                "updated_at": time.time(),
            }
        )

    @app.get("/runs/{run_id}/traceback")
    async def run_traceback(
        run_id: str,
        epoch: int | None = None,
        batch: int | None = None,
    ) -> Response:
        info = obs.registry.get(run_id)
        if info is not None:
            summary = info.summary()
        elif archive_store is not None:
            archived = archive_store.get_run(run_id)
            if archived is None:
                raise HTTPException(status_code=404, detail="unknown run_id")
            raw = archived.get("summary")
            summary = raw if isinstance(raw, dict) else {}
        else:
            raise HTTPException(status_code=404, detail="unknown run_id")

        raw_path = summary.get("traceback_path")
        if not isinstance(raw_path, str) or not raw_path:
            raise HTTPException(
                status_code=404,
                detail="no traceback captured for run",
            )
        path = Path(raw_path)
        if epoch is not None and batch is not None:
            path = path.parent / f"epoch_{epoch}_batch_{batch}.ndjson"
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail="traceback artifact not found",
            )
        return Response(
            path.read_text(encoding="utf-8"),
            media_type="application/x-ndjson",
        )

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
        limit = max(1, min(limit, _MAX_EVENTS_PER_REQUEST))
        if info is not None:
            events = list(info.events)[-limit:]
        elif archive_store is not None:
            archived = archive_store.get_run(run_id)
            if archived is None:
                raise HTTPException(status_code=404, detail="unknown run_id")
            events_raw = archived.get("events")
            if not isinstance(events_raw, list):
                raise HTTPException(status_code=500, detail="corrupt archive record")
            events = events_raw[-limit:]
        else:
            raise HTTPException(status_code=404, detail="unknown run_id")
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

    app.include_router(debate_routes.router)
    app.include_router(fitness_routes.router)
    app.include_router(mutations_routes.router)
    app.include_router(drift_routes.router)
    app.include_router(progress_routes.router)
    app.include_router(iterations_routes.router)
    app.include_router(checkpoints_routes.router)
    app.include_router(gradients_routes.router)
    app.include_router(sweep_routes.router)
    app.include_router(traceback_routes.router)
    app.include_router(groups_routes.router)
    app.include_router(agent_routes.router)
    app.include_router(archive_routes.router)
    app.include_router(benchmark_routes.router)
    app.include_router(cassettes_routes.router)

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
