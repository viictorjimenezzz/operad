"""`/runs/{run_id}/tape.json` — tape-entry snapshots for Trainer debugging."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(tags=["tape"])


def _not_found(reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "reason": reason},
    )


@router.get("/runs/{run_id}/tape.json")
async def get_tape(request: Request, run_id: str) -> JSONResponse:
    info = request.app.state.observer.registry.get(run_id)
    if info is None:
        return _not_found("unknown run_id")
    return JSONResponse({"entries": list(info.tape_entries)})


__all__ = ["router"]
