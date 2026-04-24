"""`/runs/{run_id}/fitness.{json,sse}` — best / mean / spread per generation."""

from __future__ import annotations

from statistics import fmean
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import per_run_sse


router = APIRouter(tags=["fitness"])

_GEN_KINDS = ("generation", "iteration")


@router.get("/runs/{run_id}/fitness.json")
async def fitness_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    if obs.registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    entries = [_to_entry(env) for env in obs.registry.iter_events(run_id)]
    entries = [e for e in entries if e is not None]
    entries.sort(key=lambda e: (e["gen_index"], e["timestamp"]))
    return JSONResponse(entries)


@router.get("/runs/{run_id}/fitness.sse")
async def fitness_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind=_GEN_KINDS,
            transform=_transform_or_ping,
        )
    )


def _transform_or_ping(env: dict[str, Any]) -> dict[str, Any]:
    entry = _to_entry(env)
    return entry or {"skipped": True}


def _to_entry(env: dict[str, Any]) -> dict[str, Any] | None:
    """Shape an algo-event envelope into a fitness chart row.

    Accepts `generation` events (with `population_scores`) and the
    subset of `iteration` events that carry a `score` key (SelfRefine,
    VerifierLoop). Returns None for events that carry no scoring signal
    (e.g. PromptDrift iterations).
    """
    if env.get("type") != "algo_event":
        return None
    if env.get("kind") not in _GEN_KINDS:
        return None
    payload = env.get("payload") or {}
    timestamp = env.get("finished_at") or env.get("started_at") or 0.0

    scores = payload.get("population_scores")
    if isinstance(scores, list) and scores:
        numeric = [float(s) for s in scores if isinstance(s, (int, float))]
        if not numeric:
            return None
        return {
            "gen_index": int(
                payload.get("gen_index", payload.get("iter_index", 0))
            ),
            "best": max(numeric),
            "mean": fmean(numeric),
            "worst": min(numeric),
            "population_scores": numeric,
            "timestamp": timestamp,
        }

    if env.get("kind") == "iteration":
        score = payload.get("score")
        if isinstance(score, (int, float)):
            return {
                "gen_index": int(payload.get("iter_index", 0)),
                "best": float(score),
                "mean": float(score),
                "worst": float(score),
                "population_scores": [float(score)],
                "timestamp": timestamp,
            }
    return None


__all__ = ["router"]
