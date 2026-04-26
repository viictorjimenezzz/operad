"""`/cassettes` routes: discovery, replay, determinism checks, previews."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..cassette_replay import (
    CassettePathError,
    cassette_root_from_env,
    determinism_diff,
    discover_cassettes,
    iter_normalized_envelopes,
    preview_envelopes,
    replay_run_id,
    resolve_cassette_path,
)
from ..observer import WebDashboardObserver


router = APIRouter(tags=["cassettes"])


class ReplayRequest(BaseModel):
    path: str = Field(min_length=1)
    run_id_override: str | None = Field(default=None)


class DeterminismRequest(BaseModel):
    path: str = Field(min_length=1)


@router.get("/cassettes")
async def list_cassettes() -> JSONResponse:
    root = cassette_root_from_env()
    return JSONResponse(discover_cassettes(root))


@router.get("/cassettes/preview")
async def cassette_preview(
    path: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> JSONResponse:
    root = cassette_root_from_env()
    try:
        cassette_path = resolve_cassette_path(root, path)
    except CassettePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = replay_run_id(cassette_path, run_id_override="cassette-preview")
    envelopes = preview_envelopes(cassette_path, run_id=run_id, limit=limit)
    return JSONResponse({"path": path, "events": envelopes})


@router.post("/cassettes/replay")
async def replay_cassette(
    req: ReplayRequest,
    request: Request,
    delay_ms: int = Query(default=50, ge=0, le=5_000),
) -> JSONResponse:
    root = cassette_root_from_env()
    try:
        cassette_path = resolve_cassette_path(root, req.path)
    except CassettePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    obs: WebDashboardObserver = request.app.state.observer
    run_id = replay_run_id(cassette_path, run_id_override=req.run_id_override)

    emitted = 0
    for envelope in iter_normalized_envelopes(
        cassette_path,
        run_id=run_id,
        deterministic=False,
    ):
        await obs.broadcast(envelope)
        emitted += 1
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    return JSONResponse({"run_id": run_id, "emitted": emitted})


@router.post("/cassettes/determinism-check")
async def cassette_determinism(req: DeterminismRequest) -> JSONResponse:
    root = cassette_root_from_env()
    try:
        cassette_path = resolve_cassette_path(root, req.path)
    except CassettePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result: dict[str, Any] = determinism_diff(cassette_path)
    return JSONResponse(result)
