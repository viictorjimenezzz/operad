"""Archive API backed by the SQLite run mirror."""

from __future__ import annotations

import json
from typing import Iterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..observer import WebDashboardObserver
from ..persistence import SQLiteRunArchive


router = APIRouter()


def _archive_store(request: Request) -> SQLiteRunArchive:
    store = getattr(request.app.state, "archive_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="archive store unavailable")
    return store


def _observer(request: Request) -> WebDashboardObserver:
    obs = getattr(request.app.state, "observer", None)
    if obs is None:
        raise HTTPException(status_code=500, detail="observer missing")
    return obs


@router.get("/api/archive")
async def archive_list(
    request: Request,
    from_ts: float | None = Query(default=None, alias="from"),
    to_ts: float | None = Query(default=None, alias="to"),
    algorithm: str | None = None,
    limit: int = 100,
) -> JSONResponse:
    rows = _archive_store(request).list_runs(
        from_ts=from_ts,
        to_ts=to_ts,
        algorithm=algorithm,
        limit=limit,
    )
    return JSONResponse(rows)


@router.get("/api/archive/{run_id}")
async def archive_detail(request: Request, run_id: str) -> JSONResponse:
    record = _archive_store(request).get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return JSONResponse(record)


@router.delete("/api/archive/{run_id}")
async def archive_delete(request: Request, run_id: str) -> JSONResponse:
    _archive_store(request).delete_run(run_id)
    return JSONResponse({"ok": True})


@router.post("/api/archive/{run_id}/restore")
async def archive_restore(request: Request, run_id: str) -> JSONResponse:
    record = _archive_store(request).get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    summary = record.get("summary")
    events = record.get("events")
    if not isinstance(summary, dict) or not isinstance(events, list):
        raise HTTPException(status_code=500, detail="corrupt archive record")
    info = _observer(request).registry.restore_snapshot(summary=summary, events=events)
    return JSONResponse({"ok": True, "run": info.summary()})


@router.post("/api/archive/_export")
async def archive_export(request: Request, format: str = "jsonl") -> StreamingResponse:
    if format != "jsonl":
        raise HTTPException(status_code=400, detail="format must be 'jsonl'")
    records = _archive_store(request).iter_export_records()

    def _iter_jsonl() -> Iterator[str]:
        for record in records:
            yield json.dumps(record, default=str) + "\n"

    return StreamingResponse(_iter_jsonl(), media_type="application/x-ndjson")


__all__ = ["router"]
