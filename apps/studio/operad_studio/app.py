"""FastAPI app for Studio - labeling UI + training launcher (SPA-served)."""

from __future__ import annotations

import asyncio
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .jobs import list_jobs, read_rows, save_rating
from .training import TrainingLauncher


_PKG_DIR = Path(__file__).resolve().parent
_WEB_DIR = _PKG_DIR / "web"
_WEB_INDEX = _WEB_DIR / "index.html"
_WEB_ASSETS = _WEB_DIR / "assets"

_SSE_HEARTBEAT_SECONDS = 15.0


def _studio_version() -> str:
    try:
        return version("operad-studio")
    except PackageNotFoundError:
        return "0.0.0"


def create_app(
    *,
    data_dir: Path,
    agent_bundle: Path | None = None,
    dashboard_port: int | None = None,
    launcher: TrainingLauncher | None = None,
    runner: Any = None,
) -> FastAPI:
    """Build the Studio FastAPI app.

    ``runner`` is injected by tests to stub `Trainer.fit`; production
    code leaves it ``None`` so the default runner (which instantiates a
    real `Trainer.load` + `HumanFeedbackLoss`) runs.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="operad-studio")
    app.state.data_dir = data_dir
    app.state.agent_bundle = Path(agent_bundle) if agent_bundle else None
    app.state.dashboard_port = dashboard_port
    app.state.launcher = launcher or TrainingLauncher()
    app.state.runner = runner

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
        return JSONResponse(
            {
                "mode": "studio",
                "version": _studio_version(),
                "dataDir": str(data_dir),
                "dashboardPort": app.state.dashboard_port,
            }
        )

    @app.get("/jobs")
    async def jobs() -> JSONResponse:
        items = list_jobs(data_dir)
        return JSONResponse(
            [
                {
                    "name": j.name,
                    "total_rows": j.total_rows,
                    "rated_rows": j.rated_rows,
                    "unrated": j.unrated,
                }
                for j in items
            ]
        )

    @app.get("/jobs/{job_name}/rows")
    async def job_rows(job_name: str) -> JSONResponse:
        path = _job_path(data_dir, job_name)
        rows = read_rows(path)
        return JSONResponse(
            {
                "rows": [
                    {
                        "id": r.id,
                        "index": r.index,
                        "run_id": r.run_id,
                        "agent_path": r.agent_path,
                        "input": r.input,
                        "expected": r.expected,
                        "predicted": r.predicted,
                        "rating": r.rating,
                        "rationale": r.rationale,
                        "written_at": r.written_at,
                    }
                    for r in rows
                ],
                "total": len(rows),
                "rated": sum(1 for r in rows if r.rating is not None),
            }
        )

    @app.post("/jobs/{job_name}/rows/{row_id}")
    async def rate_row(
        job_name: str,
        row_id: str,
        rating: Optional[int] = Form(None),
        rationale: Optional[str] = Form(None),
    ) -> JSONResponse:
        if rating is not None and not (1 <= rating <= 5):
            raise HTTPException(
                status_code=400, detail="rating must be between 1 and 5"
            )
        path = _job_path(data_dir, job_name)
        ok = save_rating(
            path, row_id=row_id, rating=rating, rationale=rationale
        )
        if not ok:
            raise HTTPException(status_code=404, detail="row not found")
        return JSONResponse({"ok": True})

    @app.post("/jobs/{job_name}/train")
    async def train(
        request: Request,
        job_name: str,
        epochs: int = Form(1),
        lr: float = Form(1.0),
    ) -> JSONResponse:
        path = _job_path(data_dir, job_name)
        bundle = app.state.agent_bundle
        if bundle is None:
            raise HTTPException(
                status_code=400,
                detail="--agent-bundle was not provided at CLI startup",
            )
        launcher: TrainingLauncher = app.state.launcher
        started = await launcher.start(
            job_name,
            bundle_path=bundle,
            ratings_path=path,
            data_dir=data_dir,
            epochs=epochs,
            lr=lr,
            dashboard_port=app.state.dashboard_port,
            runner=app.state.runner,
        )
        if not started:
            raise HTTPException(
                status_code=409, detail="training already running for this job"
            )
        return JSONResponse({"ok": True}, status_code=202)

    @app.get("/jobs/{job_name}/train/stream")
    async def train_stream(request: Request, job_name: str) -> EventSourceResponse:
        launcher: TrainingLauncher = app.state.launcher
        return EventSourceResponse(
            _stream_events(request, launcher, job_name)
        )

    @app.get("/jobs/{job_name}/download")
    async def download(job_name: str) -> FileResponse:
        path = _job_path(data_dir, job_name)
        if not path.exists():
            raise HTTPException(status_code=404, detail="job not found")
        return FileResponse(path, filename=f"{job_name}.jsonl")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(_render_shell())

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_catch_all(full_path: str) -> Response:
        del full_path
        return HTMLResponse(_render_shell())

    return app


def _render_shell() -> str:
    if _WEB_INDEX.is_file():
        return _WEB_INDEX.read_text(encoding="utf-8")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>operad - studio</title></head><body>"
        "<h1>operad</h1>"
        "<p>frontend bundle not built. Run "
        "<code>make build-frontend</code> or <code>cd apps/frontend &amp;&amp; pnpm dev:studio</code>.</p>"
        "</body></html>"
    )


def _job_path(data_dir: Path, job_name: str) -> Path:
    if "/" in job_name or ".." in job_name:
        raise HTTPException(status_code=400, detail="invalid job name")
    return data_dir / f"{job_name}.jsonl"


async def _stream_events(
    request: Request, launcher: TrainingLauncher, job_name: str
) -> AsyncIterator[dict[str, str]]:
    queue = launcher.subscribe(job_name)
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=_SSE_HEARTBEAT_SECONDS
                )
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": "message", "data": json.dumps(event, default=str)}
            if event.get("kind") in ("finished", "error"):
                return
    finally:
        launcher.unsubscribe(job_name, queue)


__all__ = ["create_app"]
