"""`/runs/{run_id}/gradients.{json,sse}` — TextualGradient critique log."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["gradients"])


@router.get("/runs/{run_id}/gradients.json")
async def gradients_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    entries = [
        _to_entry(env)
        for env in iter_run_events(
            request,
            obs,
            run_id, kind="gradient_applied", algorithm_path="Trainer"
        )
    ]
    entries.sort(key=lambda e: (e["epoch"], e["batch"]))
    return JSONResponse(entries)


@router.get("/runs/{run_id}/gradients.sse")
async def gradients_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="gradient_applied",
            algorithm_path="Trainer",
            transform=_to_entry,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    return {
        "epoch": int(payload.get("epoch", 0)),
        "batch": int(payload.get("batch", 0)),
        "message": payload.get("message", ""),
        "severity": float(payload.get("severity", 0.0)),
        "target_paths": list(payload.get("target_paths") or []),
        "by_field": dict(payload.get("by_field") or {}),
        "applied_diff": payload.get("applied_diff", ""),
        "timestamp": env.get("finished_at") or env.get("started_at") or 0.0,
    }


__all__ = ["router"]
