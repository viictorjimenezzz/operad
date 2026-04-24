"""`/runs/{run_id}/drift.{json,sse}` — PromptDrift epoch-wise hash timeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import per_run_sse


router = APIRouter(tags=["drift"])


@router.get("/runs/{run_id}/drift.json")
async def drift_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    if obs.registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    entries = [
        _to_entry(env)
        for env in obs.registry.iter_events(
            run_id, kind="iteration", algorithm_path="PromptDrift"
        )
    ]
    entries.sort(key=lambda e: e["epoch"])
    return JSONResponse(entries)


@router.get("/runs/{run_id}/drift.sse")
async def drift_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="iteration",
            algorithm_path="PromptDrift",
            transform=_to_entry,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    return {
        "epoch": int(payload.get("epoch", 0)),
        "hash_before": payload.get("hash_before", ""),
        "hash_after": payload.get("hash_after", ""),
        "changed_params": list(payload.get("changed_params") or []),
        "delta_count": int(payload.get("delta_count", 0)),
        "timestamp": env.get("finished_at") or env.get("started_at") or 0.0,
    }


__all__ = ["router"]
