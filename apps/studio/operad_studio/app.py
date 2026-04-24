"""FastAPI app for Studio — labeling UI + training launcher."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from .jobs import list_jobs, read_rows, save_rating
from .training import TrainingLauncher


_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _PKG_DIR / "templates"
_STATIC_DIR = _PKG_DIR / "static"

_SSE_HEARTBEAT_SECONDS = 15.0


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

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        jobs = list_jobs(data_dir)
        return templates.TemplateResponse(
            request, "index.html", {"jobs": jobs, "data_dir": str(data_dir)}
        )

    @app.get("/jobs/{job_name}", response_class=HTMLResponse)
    async def job_view(request: Request, job_name: str) -> HTMLResponse:
        path = _job_path(data_dir, job_name)
        rows = read_rows(path)
        return templates.TemplateResponse(
            request,
            "job.html",
            {
                "job_name": job_name,
                "rows": rows,
                "total": len(rows),
                "rated": sum(1 for r in rows if r.rating is not None),
            },
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

    return app


def _job_path(data_dir: Path, job_name: str) -> Path:
    # Prevent path traversal.
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
