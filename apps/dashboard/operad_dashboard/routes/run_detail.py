"""`GET /runs/{run_id}` — run-detail page with per-panel partials."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..observer import WebDashboardObserver


router = APIRouter(tags=["run-detail"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str) -> HTMLResponse:
    obs: WebDashboardObserver = request.app.state.observer
    info = obs.registry.get(run_id)
    if info is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    langfuse_base: str | None = getattr(request.app.state, "langfuse_url", None)
    langfuse_trace_url = (
        f"{langfuse_base}/trace/{run_id}" if langfuse_base else None
    )
    return _templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run_id": run_id,
            "state": info.state,
            "has_graph": info.mermaid is not None,
            "langfuse_trace_url": langfuse_trace_url,
        },
    )
