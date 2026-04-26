"""`/runs/{run_id}/checkpoints.{json,sse}` — per-epoch checkpoint timeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["checkpoints"])


@router.get("/runs/{run_id}/checkpoints.json")
async def checkpoints_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    entries = [
        _to_entry(env)
        for env in iter_run_events(
            request,
            obs,
            run_id, kind="iteration", algorithm_path="Trainer"
        )
        if (env.get("payload") or {}).get("phase") == "epoch_end"
    ]
    entries.sort(key=lambda e: e["epoch"])
    _mark_best(entries)
    return JSONResponse(entries)


@router.get("/runs/{run_id}/checkpoints.sse")
async def checkpoints_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer
    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="iteration",
            algorithm_path="Trainer",
            transform=_to_entry_if_epoch_end,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    train_loss = payload.get("train_loss")
    val_loss = payload.get("val_loss")
    score = val_loss if val_loss is not None else train_loss
    return {
        "epoch": int(payload.get("epoch", 0)),
        "train_loss": train_loss,
        "val_loss": val_loss,
        "score": score,
        "is_best": False,
    }


def _to_entry_if_epoch_end(env: dict[str, Any]) -> dict[str, Any] | None:
    payload = env.get("payload") or {}
    if payload.get("phase") != "epoch_end":
        return None
    return _to_entry(env)


def _mark_best(entries: list[dict[str, Any]]) -> None:
    best_idx = None
    best_score: float | None = None
    for i, e in enumerate(entries):
        score = e["score"]
        if score is not None and (best_score is None or score < best_score):
            best_score = score
            best_idx = i
    if best_idx is not None:
        entries[best_idx]["is_best"] = True


__all__ = ["router"]
