"""`/runs/{run_id}/sweep.{json,sse}` — Sweep parameter-grid snapshot."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import per_run_sse


router = APIRouter(tags=["sweep"])

_RELEVANT_KINDS = ("algo_start", "cell", "algo_end", "algo_error")
_ALGORITHM_PATH = "Sweep"


@router.get("/runs/{run_id}/sweep.json")
async def sweep_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    if obs.registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    snapshot = _compute_snapshot(obs.registry.iter_events(run_id))
    return JSONResponse(snapshot)


@router.get("/runs/{run_id}/sweep.sse")
async def sweep_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer

    def _snapshot(_env: dict[str, Any]) -> dict[str, Any]:
        return _compute_snapshot(obs.registry.iter_events(run_id))

    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind=_RELEVANT_KINDS,
            algorithm_path=_ALGORITHM_PATH,
            transform=_snapshot,
        )
    )


def _compute_snapshot(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold a run's Sweep events into a grid snapshot.

    Returns:
        {
          "cells":            list[{cell_index, parameters, score}],
          "axes":             list[{name, values}],
          "score_range":      [min, max] | null,
          "best_cell_index":  int | null,
          "total_cells":      int,
          "finished":         bool,
        }
    """
    cells_by_index: dict[int, dict[str, Any]] = {}
    best_cell_index: int | None = None
    total_cells: int = 0
    finished = False

    for env in events:
        if env.get("type") != "algo_event":
            continue
        if env.get("algorithm_path") != _ALGORITHM_PATH:
            continue
        kind = env.get("kind")
        payload = env.get("payload") or {}

        if kind == "cell":
            idx = payload.get("cell_index")
            if isinstance(idx, int):
                cells_by_index[idx] = {
                    "cell_index": idx,
                    "parameters": payload.get("parameters") or {},
                    "score": payload.get("score"),
                }
        elif kind == "algo_end":
            total_cells = int(payload.get("cells", 0))
            finished = True
        elif kind == "algo_error":
            finished = True

    cells = [cells_by_index[i] for i in sorted(cells_by_index)]

    # Derive axes: unique sorted values per parameter name, in key order.
    param_values: dict[str, list[Any]] = {}
    for cell in cells:
        for k, v in cell["parameters"].items():
            if k not in param_values:
                param_values[k] = []
            if v not in param_values[k]:
                param_values[k].append(v)
    axes = [{"name": k, "values": sorted(vs, key=str)} for k, vs in param_values.items()]

    # Score range and best cell (skip None scores).
    scores = [c["score"] for c in cells if c["score"] is not None]
    score_range = [min(scores), max(scores)] if scores else None
    if scores:
        best_score = max(scores)
        for cell in cells:
            if cell["score"] == best_score:
                best_cell_index = cell["cell_index"]
                break

    return {
        "cells": cells,
        "axes": axes,
        "score_range": score_range,
        "best_cell_index": best_cell_index,
        "total_cells": total_cells or len(cells),
        "finished": finished,
    }


__all__ = ["router"]
