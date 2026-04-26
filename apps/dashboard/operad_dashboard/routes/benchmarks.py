"""`/benchmarks/*` — benchmark ingest, listing, detail, tagging, delete."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..benchmark_store import BenchmarkStore, compute_delta_rows


router = APIRouter(tags=["benchmarks"])


def _store(request: Request) -> BenchmarkStore:
    return request.app.state.benchmark_store


@router.post("/benchmarks/_ingest")
async def benchmarks_ingest(request: Request) -> JSONResponse:
    payload = await request.json()
    store = _store(request)
    try:
        bench_id = store.ingest(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse({"id": bench_id})


@router.get("/benchmarks")
async def benchmarks_list(request: Request) -> JSONResponse:
    return JSONResponse(_store(request).list())


@router.get("/benchmarks/{bench_id}")
async def benchmarks_detail(request: Request, bench_id: str) -> JSONResponse:
    store = _store(request)
    detail = store.get(bench_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown benchmark id")

    baseline: dict[str, Any] | None = None
    delta_rows: list[dict[str, Any]] = []

    baseline_id = store.latest_tagged_id()
    if baseline_id is not None and baseline_id != bench_id:
        baseline_detail = store.get(baseline_id)
        if baseline_detail is not None:
            baseline_report = baseline_detail["report"]
            delta_rows = compute_delta_rows(detail["report"], baseline_report)
            baseline = {
                "id": baseline_id,
                "name": baseline_detail["name"],
                "tag": baseline_detail["tag"],
                "created_at": baseline_detail["created_at"],
            }

    return JSONResponse(
        {
            **detail,
            "baseline": baseline,
            "delta": delta_rows,
        }
    )


@router.post("/benchmarks/{bench_id}/tag")
async def benchmarks_tag(request: Request, bench_id: str) -> JSONResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")
    tag = payload.get("tag")
    if not isinstance(tag, str) or not tag.strip():
        raise HTTPException(status_code=422, detail="tag must be a non-empty string")

    ok = _store(request).tag(bench_id, tag.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="unknown benchmark id")
    return JSONResponse({"ok": True})


@router.delete("/benchmarks/{bench_id}")
async def benchmarks_delete(request: Request, bench_id: str) -> JSONResponse:
    ok = _store(request).delete(bench_id)
    if not ok:
        raise HTTPException(status_code=404, detail="unknown benchmark id")
    return JSONResponse({"ok": True})


__all__ = ["router"]
