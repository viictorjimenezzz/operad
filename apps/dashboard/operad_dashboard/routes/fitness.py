"""`/runs/{run_id}/fitness.{json,sse}` — best / mean / spread per generation."""

from __future__ import annotations

from statistics import fmean
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["fitness"])

_GEN_KINDS = ("generation", "iteration", "batch_end")


@router.get("/runs/{run_id}/fitness.json")
async def fitness_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    entries = [_to_entry(env) for env in iter_run_events(request, obs, run_id)]
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
    VerifierAgent). Returns None for events that carry no scoring signal
    (e.g. PromptDrift iterations).
    """
    if env.get("type") != "algo_event":
        return None
    if env.get("kind") not in _GEN_KINDS:
        return None
    payload = env.get("payload") or {}
    timestamp = env.get("finished_at") or env.get("started_at") or 0.0

    if env.get("algorithm_path") == "Trainer":
        if env.get("kind") == "batch_end":
            train_loss = payload.get("train_loss")
            if not isinstance(train_loss, (int, float)):
                return None
            lr = payload.get("lr")
            return {
                "gen_index": float(payload.get("step", 0)),
                "best": float(train_loss),
                "mean": float(train_loss),
                "worst": float(train_loss),
                "train_loss": float(train_loss),
                "val_loss": None,
                "lr": float(lr) if isinstance(lr, (int, float)) else None,
                "population_scores": [float(train_loss)],
                "timestamp": timestamp,
            }
        if env.get("kind") == "iteration" and payload.get("phase") == "epoch_end":
            train_loss = payload.get("train_loss")
            val_loss = payload.get("val_loss")
            if not isinstance(train_loss, (int, float)):
                return None
            lr = payload.get("lr")
            score = (
                float(val_loss)
                if isinstance(val_loss, (int, float))
                else float(train_loss)
            )
            return {
                "gen_index": int(payload.get("epoch", 0)),
                "best": float(train_loss),
                "mean": float(train_loss),
                "worst": float(train_loss),
                "train_loss": float(train_loss),
                "val_loss": float(val_loss) if isinstance(val_loss, (int, float)) else None,
                "lr": float(lr) if isinstance(lr, (int, float)) else None,
                "population_scores": [score],
                "timestamp": timestamp,
            }

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
                "train_loss": None,
                "val_loss": None,
                "lr": None,
                "population_scores": [float(score)],
                "timestamp": timestamp,
            }
    return None


__all__ = ["router"]
