"""`/runs/{run_id}/progress.{json,sse}` — training progress snapshot."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["progress"])

_RELEVANT_KINDS = ("algo_start", "algo_end", "algo_error", "iteration", "batch_start", "batch_end")
_RELEVANT_PATHS = ("Trainer", "DataLoader")


@router.get("/runs/{run_id}/progress.json")
async def progress_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    snapshot = _compute_snapshot(iter_run_events(request, obs, run_id))
    return JSONResponse(snapshot)


@router.get("/runs/{run_id}/progress.sse")
async def progress_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer

    def _snapshot(_env: dict[str, Any]) -> dict[str, Any]:
        return _compute_snapshot(iter_run_events(request, obs, run_id))

    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind=_RELEVANT_KINDS,
            algorithm_path=_RELEVANT_PATHS,
            transform=_snapshot,
        )
    )


def _compute_snapshot(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold a run's Trainer/DataLoader events into a single progress snapshot.

    Returns a dict safe to ship on both `.json` and per-event `.sse`:

        {
          "epoch":                int,
          "epochs_total":         int | None,
          "batch":                int,
          "batches_total":        int | None,
          "elapsed_s":            float,
          "rate_batches_per_s":   float,
          "eta_s":                float | None,
          "finished":             bool,
        }
    """
    epoch = 0
    epochs_total: int | None = None
    batch = 0
    batches_total: int | None = None
    started_at: float | None = None
    last_event_at: float = 0.0
    finished = False
    batches_this_epoch = 0
    durations_ms: list[float] = []

    for env in events:
        if env.get("type") != "algo_event":
            continue
        path = env.get("algorithm_path")
        kind = env.get("kind")
        payload = env.get("payload") or {}
        ts = env.get("finished_at") or env.get("started_at") or 0.0
        if ts > last_event_at:
            last_event_at = ts

        if path == "Trainer" and kind == "algo_start":
            started_at = env.get("started_at") or started_at
            e = payload.get("epochs")
            epochs_total = int(e) if isinstance(e, int) else epochs_total
            epoch = 0
            batch = 0
            finished = False
            batches_this_epoch = 0
        elif path == "Trainer" and kind == "iteration":
            phase = payload.get("phase")
            ep = payload.get("epoch")
            if phase == "epoch_start" and isinstance(ep, int):
                if batches_total is None and batches_this_epoch > 0:
                    batches_total = batches_this_epoch
                batches_this_epoch = 0
                batch = 0
                epoch = ep
            elif phase == "epoch_end":
                if batches_total is None and batches_this_epoch > 0:
                    batches_total = batches_this_epoch
        elif path == "Trainer" and kind in ("algo_end", "algo_error"):
            finished = True
        elif path == "DataLoader" and kind == "batch_start":
            idx = payload.get("batch_index")
            if isinstance(idx, int):
                batch = idx + 1
                batches_this_epoch = batch
        elif path == "DataLoader" and kind == "batch_end":
            d = payload.get("duration_ms")
            if isinstance(d, (int, float)) and d > 0:
                durations_ms.append(float(d))

    elapsed = (last_event_at - started_at) if started_at else 0.0
    rate = _ema_rate(durations_ms)
    eta: float | None = None
    if rate > 0 and batches_total and epochs_total:
        remaining_batches = (epochs_total - epoch) * batches_total - batch
        if remaining_batches > 0:
            eta = remaining_batches / rate
    return {
        "epoch": int(epoch),
        "epochs_total": epochs_total,
        "batch": int(batch),
        "batches_total": batches_total,
        "elapsed_s": round(float(elapsed), 3),
        "rate_batches_per_s": round(float(rate), 3),
        "eta_s": round(float(eta), 3) if eta is not None else None,
        "finished": bool(finished),
    }


def _ema_rate(durations_ms: list[float]) -> float:
    if not durations_ms:
        return 0.0
    alpha = 0.3
    smoothed = 0.0
    for d in durations_ms:
        sample = 1000.0 / max(d, 1e-6)  # batches per second
        smoothed = sample if smoothed == 0.0 else alpha * sample + (1 - alpha) * smoothed
    return smoothed


__all__ = ["router"]
