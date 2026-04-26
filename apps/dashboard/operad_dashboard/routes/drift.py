"""`/runs/{run_id}/drift.{json,sse}` — PromptDrift text-diff timeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import iter_run_events, per_run_sse


router = APIRouter(tags=["drift"])


@router.get("/runs/{run_id}/drift.json")
async def drift_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    all_events = list(iter_run_events(request, obs, run_id))
    gradients = _gradient_index(all_events)
    entries = [
        _to_entry(env)
        for env in all_events
        if env.get("kind") == "iteration" and env.get("algorithm_path") == "PromptDrift"
    ]
    entries = [_attach_gradient(e, gradients) for e in entries]
    entries.sort(key=lambda e: (e["epoch"], e["timestamp"]))
    return JSONResponse(entries)


@router.get("/runs/{run_id}/drift.sse")
async def drift_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer

    def _transform(env: dict[str, Any]) -> dict[str, Any]:
        gradients = _gradient_index(obs.registry.iter_events(run_id))
        return _attach_gradient(_to_entry(env), gradients)

    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="iteration",
            algorithm_path="PromptDrift",
            transform=_transform,
        )
    )


def _to_entry(env: dict[str, Any]) -> dict[str, Any]:
    payload = env.get("payload") or {}
    changes = list(payload.get("changes") or [])
    selected_path = str(payload.get("selected_path") or "")
    selected = next((c for c in changes if c.get("path") == selected_path), None)
    if selected is None and changes:
        selected = changes[0]
    return {
        "epoch": int(payload.get("epoch", 0)),
        "before_text": (
            str(selected.get("before_text", ""))
            if selected is not None
            else str(payload.get("before_text", ""))
        ),
        "after_text": (
            str(selected.get("after_text", ""))
            if selected is not None
            else str(payload.get("after_text", ""))
        ),
        "selected_path": (
            str(selected.get("path", ""))
            if selected is not None
            else str(selected_path)
        ),
        "changes": [
            {
                "path": str(c.get("path", "")),
                "before_text": str(c.get("before_text", "")),
                "after_text": str(c.get("after_text", "")),
            }
            for c in changes
        ],
        "changed_params": list(payload.get("changed_params") or []),
        "delta_count": int(payload.get("delta_count", 0)),
        "critique": "",
        "gradient_epoch": None,
        "gradient_batch": None,
        "timestamp": env.get("finished_at") or env.get("started_at") or 0.0,
    }


def _gradient_index(events: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for env in events:
        if env.get("type") != "algo_event":
            continue
        if env.get("algorithm_path") != "Trainer":
            continue
        if env.get("kind") != "gradient_applied":
            continue
        payload = env.get("payload") or {}
        epoch = int(payload.get("epoch", -1))
        if epoch < 0:
            continue
        batch = int(payload.get("batch", 0))
        prev = out.get(epoch)
        if prev is None or batch >= int(prev.get("batch", 0)):
            out[epoch] = {
                "message": str(payload.get("message", "")),
                "epoch": epoch,
                "batch": batch,
            }
    return out


def _attach_gradient(entry: dict[str, Any], gradients: dict[int, dict[str, Any]]) -> dict[str, Any]:
    match = gradients.get(entry["epoch"])
    if match is None:
        return entry
    out = dict(entry)
    out["critique"] = match["message"]
    out["gradient_epoch"] = match["epoch"]
    out["gradient_batch"] = match["batch"]
    return out


__all__ = ["router"]
