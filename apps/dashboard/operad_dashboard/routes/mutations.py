"""`/runs/{run_id}/mutations.{json,sse}` — per-op success-rate heatmap."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..observer import WebDashboardObserver
from . import per_run_sse


router = APIRouter(tags=["mutations"])


@router.get("/runs/{run_id}/mutations.json")
async def mutations_json(request: Request, run_id: str) -> JSONResponse:
    obs: WebDashboardObserver = request.app.state.observer
    if obs.registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    matrix = _aggregate(obs.registry.iter_events(run_id))
    return JSONResponse(matrix)


@router.get("/runs/{run_id}/mutations.sse")
async def mutations_sse(request: Request, run_id: str) -> EventSourceResponse:
    obs: WebDashboardObserver = request.app.state.observer

    def _snapshot(_env: dict[str, Any]) -> dict[str, Any]:
        return _aggregate(obs.registry.iter_events(run_id))

    return EventSourceResponse(
        per_run_sse(
            request,
            obs,
            run_id,
            event_type="algo_event",
            kind="generation",
            transform=_snapshot,
        )
    )


def _aggregate(events) -> dict[str, Any]:
    """Reduce a run's generation events to aligned matrices.

    Output:
      {
        "gens":     [0, 1, 2, ...],
        "ops":      ["mutate_role", "crossover", ...],   # sorted by total attempts desc
        "success":  [[s_op0_g0, s_op0_g1, ...], ...],
        "attempts": [[a_op0_g0, a_op0_g1, ...], ...],
      }

    Ops present in any generation are included; missing cells are zero.
    Events lacking the attribution keys (pre-wave-1 runs) contribute
    nothing — the panel auto-hides in that case.
    """
    per_gen: dict[int, tuple[dict[str, int], dict[str, int]]] = {}
    op_totals: dict[str, int] = {}

    for env in events:
        if env.get("type") != "algo_event" or env.get("kind") != "generation":
            continue
        payload = env.get("payload") or {}
        gen_index = payload.get("gen_index")
        if not isinstance(gen_index, int):
            continue
        attempts = payload.get("op_attempt_counts")
        successes = payload.get("op_success_counts")
        if not isinstance(attempts, dict) or not isinstance(successes, dict):
            continue
        if not attempts and not successes:
            continue
        per_gen[gen_index] = (
            {k: int(v) for k, v in successes.items()},
            {k: int(v) for k, v in attempts.items()},
        )
        for op, n in attempts.items():
            op_totals[op] = op_totals.get(op, 0) + int(n)

    if not per_gen:
        return {"gens": [], "ops": [], "success": [], "attempts": []}

    gens = sorted(per_gen.keys())
    ops = sorted(op_totals.keys(), key=lambda op: (-op_totals[op], op))
    success_matrix = [
        [per_gen[g][0].get(op, 0) for g in gens] for op in ops
    ]
    attempts_matrix = [
        [per_gen[g][1].get(op, 0) for g in gens] for op in ops
    ]
    return {
        "gens": gens,
        "ops": ops,
        "success": success_matrix,
        "attempts": attempts_matrix,
    }


__all__ = ["router"]
