"""`/runs/{run_id}/debate.{json,sse}` — per-round proposals, critiques, scores."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["debate"])


@router.get("/runs/{run_id}/debate.json")
async def debate_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    entries = [
        _to_entry(env)
        for env in iter_run_events(
            request,
            obs,
            run_id,
            kind="round",
            algorithm_path="Debate",
        )
    ]
    entries.sort(key=lambda e: e["round_index"])
    return JSONResponse(entries)


@router.get("/runs/{run_id}/debate.sse")
async def debate_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="round",
            algorithm_path="Debate",
            transform=_to_entry,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    return {
        "round_index": int(payload.get("round_index", 0)),
        "proposals": list(payload.get("proposals") or []),
        "critiques": list(payload.get("critiques") or []),
        "scores": [float(s) for s in (payload.get("scores") or [])],
        "timestamp": env.get("finished_at") or env.get("started_at") or 0.0,
    }


__all__ = ["router"]
