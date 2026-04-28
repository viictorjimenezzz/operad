"""`/runs/{run_id}/traceback.ndjson` — PromptTraceback frame reader."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(tags=["traceback"])


def _not_found(reason: str) -> JSONResponse:
    return JSONResponse({"detail": reason}, status_code=404)


@router.get("/runs/{run_id}/traceback.ndjson")
async def get_traceback(request: Request, run_id: str) -> JSONResponse:
    info = request.app.state.observer.registry.get(run_id)
    if info is None or not info.traceback_path:
        return _not_found("no traceback for this run")
    path = Path(info.traceback_path)
    if not path.exists():
        return _not_found("traceback file missing on disk")
    frames = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return JSONResponse({"frames": frames})


__all__ = ["router"]
