"""`/runs/{run_id}/iterations.{json,sse}` — iteration events for Beam, VerifierAgent, SelfRefine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["iterations"])
_PHASE_ORDER = {
    None: 99,
    "generate": 0,
    "verify": 1,
    "refine": 2,
    "reflect": 3,
    "prune": 4,
}


@router.get("/runs/{run_id}/iterations.json")
async def iterations_json(run_id: str, request: Request) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    all_events = list(iter_run_events(request, obs, run_id))

    iteration_envs = [env for env in all_events if env.get("kind") == "iteration"]
    iteration_envs = sorted(
        iteration_envs,
        key=lambda env: (
            int((env.get("payload") or {}).get("iter_index", 0)),
            _PHASE_ORDER.get((env.get("payload") or {}).get("phase"), 98),
            float(env.get("started_at") or 0.0),
        ),
    )
    iterations = [_to_entry(env) for env in iteration_envs]

    max_iter: int | None = None
    threshold: float | None = None
    converged: bool | None = None

    for env in all_events:
        kind = env.get("kind")
        payload = env.get("payload") or {}
        if kind == "algo_start":
            if "max_iter" in payload:
                max_iter = int(payload["max_iter"])
            if "threshold" in payload:
                threshold = float(payload["threshold"])
        elif kind == "algo_end":
            if "converged" in payload:
                converged = bool(payload["converged"])

    return JSONResponse(
        {
            "iterations": iterations,
            "max_iter": max_iter,
            "threshold": threshold,
            "converged": converged,
        }
    )


@router.get("/runs/{run_id}/iterations.sse")
async def iterations_sse(run_id: str, request: Request) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="iteration",
            transform=_to_entry,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    return {
        "iter_index": int(payload.get("iter_index", 0)),
        "phase": payload.get("phase") or None,
        "score": float(payload["score"]) if "score" in payload else None,
        "text": payload.get("text") or None,
        "metadata": {
            k: v
            for k, v in payload.items()
            if k not in ("iter_index", "phase", "score", "text")
        },
    }


__all__ = ["router"]
