"""Per-agent dashboard endpoints used by the agent-detail view."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import json
from pathlib import Path
import time
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from operad.core.config import Configuration
from operad.core.graph import TypeRegistry, from_json, to_io_graph
from operad.core.example import Example
from operad.runtime.observers.base import suppress_notifications

from .runs import RunInfo


router = APIRouter(tags=["agent-view"])

_DEFAULT_EVENT_LIMIT = 200
_MAX_EVENT_LIMIT = 500
_PROMPT_CACHE_MAX = 128
_PROMPT_CACHE: OrderedDict[tuple[str, str, float], dict[str, Any]] = OrderedDict()


@dataclass
class _RunContext:
    run_id: str
    info: RunInfo | None
    summary: dict[str, Any]
    events: list[dict[str, Any]]
    graph_json: dict[str, Any] | None


@dataclass
class _Invocation:
    row: dict[str, Any]
    start: dict[str, Any] | None
    terminal: dict[str, Any]


class _InvokeOverrides(BaseModel):
    role: str | None = None
    task: str | None = None
    rules: list[str] | None = None
    examples: list[dict[str, Any]] | None = None
    config: dict[str, Any] | None = None


class _InvokeBody(BaseModel):
    input: dict[str, Any]
    overrides: _InvokeOverrides | None = None
    stream: bool = False


def _not_found(reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "reason": reason},
    )


def _resolve_run_context(request: Request, run_id: str) -> _RunContext | None:
    obs = request.app.state.observer
    info = obs.registry.get(run_id)
    if info is not None:
        return _RunContext(
            run_id=run_id,
            info=info,
            summary=info.summary(),
            events=list(info.events),
            graph_json=info.graph_json,
        )
    store = getattr(request.app.state, "archive_store", None)
    if store is None:
        return None
    record = store.get_run(run_id)
    if record is None:
        return None
    summary = record.get("summary")
    events = record.get("events")
    if not isinstance(summary, dict) or not isinstance(events, list):
        return None
    graph_json = summary.get("graph_json")
    return _RunContext(
        run_id=run_id,
        info=None,
        summary=summary,
        events=[e for e in events if isinstance(e, dict)],
        graph_json=graph_json if isinstance(graph_json, dict) else None,
    )


def _graph_from_json(graph_json: dict[str, Any]) -> dict[str, Any]:
    registry = TypeRegistry()
    graph = from_json(graph_json, registry=registry)
    return to_io_graph(graph)


def _fallback_io_graph(graph_json: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for node in graph_json.get("nodes") or []:
        if not isinstance(node, dict) or node.get("kind") != "leaf":
            continue
        input_key = str(node.get("input") or "")
        output_key = str(node.get("output") or "")
        if input_key and input_key not in nodes:
            nodes[input_key] = {"key": input_key, "name": input_key.rsplit(".", 1)[-1], "fields": []}
        if output_key and output_key not in nodes:
            nodes[output_key] = {"key": output_key, "name": output_key.rsplit(".", 1)[-1], "fields": []}
        path = str(node.get("path") or "")
        edges.append(
            {
                "agent_path": path,
                "class_name": path.rsplit(".", 1)[-1],
                "kind": "leaf",
                "from": input_key,
                "to": output_key,
                "composite_path": _composite_path_from_path(path, graph_json.get("root")),
            }
        )
    return {
        "root": graph_json.get("root"),
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def _composite_path_from_path(path: str, root: Any) -> str | None:
    if not path or "." not in path:
        return None
    parent = path.rsplit(".", 1)[0]
    root_str = str(root) if isinstance(root, str) else ""
    if parent == root_str:
        return None
    return parent


def _io_graph_payload(ctx: _RunContext) -> dict[str, Any]:
    graph_json = ctx.graph_json
    if graph_json is None:
        for env in ctx.events:
            metadata = env.get("metadata")
            if isinstance(metadata, dict):
                graph = metadata.get("graph")
                if isinstance(graph, dict):
                    graph_json = graph
                    break
    if graph_json is None:
        return {"root": None, "nodes": [], "edges": []}
    try:
        return _graph_from_json(graph_json)
    except Exception:
        return _fallback_io_graph(graph_json)


def _root_agent_path(ctx: _RunContext) -> str | None:
    root = ctx.summary.get("root_agent_path")
    if isinstance(root, str) and root:
        return root
    for env in ctx.events:
        if env.get("type") != "agent_event" or env.get("kind") != "start":
            continue
        metadata = env.get("metadata")
        if isinstance(metadata, dict) and metadata.get("is_root"):
            path = env.get("agent_path")
            if isinstance(path, str) and path:
                return path
    return None


def _events_for_path(events: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for env in events:
        if env.get("type") != "agent_event":
            continue
        if env.get("agent_path") == path:
            out.append(env)
    return out


def _env_sort_key(env: dict[str, Any]) -> tuple[float, float]:
    started = env.get("started_at")
    finished = env.get("finished_at")
    start_v = float(started) if isinstance(started, (int, float)) else 0.0
    fin_v = float(finished) if isinstance(finished, (int, float)) else 0.0
    return start_v, fin_v


def _error_repr(env: dict[str, Any]) -> str | None:
    err = env.get("error")
    if not isinstance(err, dict):
        return None
    typ = err.get("type")
    msg = err.get("message")
    if typ is None and msg is None:
        return None
    return f"{typ or 'Error'}: {msg or ''}".strip()


def _build_invocations(
    *,
    run_id: str,
    events: list[dict[str, Any]],
    agent_path: str,
    langfuse_url: str | None,
) -> list[_Invocation]:
    agent_events = sorted(_events_for_path(events, agent_path), key=_env_sort_key)
    pending: list[dict[str, Any]] = []
    out: list[_Invocation] = []

    for env in agent_events:
        kind = env.get("kind")
        if kind == "start":
            pending.append(env)
            continue
        if kind not in {"end", "error"}:
            continue
        start = pending.pop(0) if pending else None
        output = env.get("output") if isinstance(env.get("output"), dict) else {}
        metadata = env.get("metadata") if isinstance(env.get("metadata"), dict) else {}
        started_at = (
            float(start["started_at"])
            if start is not None and isinstance(start.get("started_at"), (int, float))
            else float(env.get("started_at") or 0.0)
        )
        finished_at = env.get("finished_at")
        latency_ms: float | None = None
        if isinstance(finished_at, (int, float)):
            latency_ms = max(0.0, (float(finished_at) - started_at) * 1000.0)
        elif isinstance(output.get("latency_ms"), (int, float)):
            latency_ms = float(output.get("latency_ms"))
        script = None
        if start is not None:
            start_meta = start.get("metadata")
            if isinstance(start_meta, dict) and isinstance(start_meta.get("script"), str):
                script = start_meta.get("script")
        out.append(
            _Invocation(
                row={
                    "id": f"{agent_path}:{len(out)}",
                    "started_at": started_at,
                    "finished_at": float(finished_at) if isinstance(finished_at, (int, float)) else None,
                    "latency_ms": latency_ms,
                    "prompt_tokens": int(output.get("prompt_tokens") or 0),
                    "completion_tokens": int(output.get("completion_tokens") or 0),
                    "hash_prompt": output.get("hash_prompt"),
                    "hash_input": output.get("hash_input"),
                    "hash_content": metadata.get("hash_content"),
                    "status": "ok" if kind == "end" else "error",
                    "error": None if kind == "end" else _error_repr(env),
                    "langfuse_url": (
                        f"{langfuse_url}/trace/{run_id}" if langfuse_url is not None else None
                    ),
                    "script": script,
                    "input": start.get("input") if isinstance(start, dict) else None,
                    "output": output.get("response"),
                },
                start=start,
                terminal=env,
            )
        )
    return out


def _latest_terminal_metadata(events: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    for env in reversed(events):
        if env.get("type") != "agent_event":
            continue
        if env.get("agent_path") != path:
            continue
        if env.get("kind") != "end":
            continue
        metadata = env.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    return None


def _prompt_cache_get(key: tuple[str, str, float]) -> dict[str, Any] | None:
    hit = _PROMPT_CACHE.get(key)
    if hit is None:
        return None
    _PROMPT_CACHE.move_to_end(key)
    return hit


def _prompt_cache_set(key: tuple[str, str, float], value: dict[str, Any]) -> None:
    _PROMPT_CACHE[key] = value
    _PROMPT_CACHE.move_to_end(key)
    while len(_PROMPT_CACHE) > _PROMPT_CACHE_MAX:
        _PROMPT_CACHE.popitem(last=False)


def _extract_attr(value: Any, attr: str) -> tuple[bool, Any]:
    cur = value
    for part in attr.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return False, None
            cur = cur[part]
            continue
        return False, None
    return True, cur


def _value_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _error(status_code: int, reason: str, *, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": code, "reason": reason})


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
            continue
        merged[key] = value
    return merged


def _apply_overrides(agent: Any, overrides: _InvokeOverrides | None) -> None:
    if overrides is None:
        return
    if overrides.role is not None:
        agent.role = overrides.role
    if overrides.task is not None:
        agent.task = overrides.task
    if overrides.rules is not None:
        agent.rules = list(overrides.rules)
    if overrides.examples is not None:
        agent.examples = [
            Example(
                input=agent.input.model_validate(e.get("input")),
                output=agent.output.model_validate(e.get("output")),
            )
            for e in overrides.examples
        ]
    if overrides.config is not None:
        if agent.config is None:
            raise ValueError("config overrides require a live config on the target agent")
        merged = _deep_merge(agent.config.model_dump(mode="json"), overrides.config)
        agent.config = Configuration.model_validate(merged)


def _append_experiment_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str))
        handle.write("\n")


@router.get("/runs/{run_id}/io_graph")
async def io_graph(request: Request, run_id: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    return JSONResponse(_io_graph_payload(ctx))


@router.get("/runs/{run_id}/invocations")
async def root_invocations(request: Request, run_id: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    root_path = _root_agent_path(ctx)
    if root_path is None:
        return _not_found("root agent path unknown")
    langfuse_url = getattr(request.app.state, "langfuse_url", None)
    invocations = _build_invocations(
        run_id=run_id,
        events=ctx.events,
        agent_path=root_path,
        langfuse_url=langfuse_url,
    )
    return JSONResponse(
        {"agent_path": root_path, "invocations": [inv.row for inv in invocations]}
    )


@router.get("/runs/{run_id}/agent/{path:path}/meta")
async def agent_meta(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    io_graph = _io_graph_payload(ctx)
    edge = next((e for e in io_graph.get("edges", []) if e.get("agent_path") == path), None)
    if edge is None:
        return _not_found("unknown agent_path")
    metadata = _latest_terminal_metadata(ctx.events, path)
    if metadata is None:
        return _not_found("unknown agent_path")
    nodes_by_key = {n.get("key"): n for n in io_graph.get("nodes", []) if isinstance(n, dict)}
    langfuse_base = getattr(request.app.state, "langfuse_url", None)
    return JSONResponse(
        {
            "agent_path": path,
            "class_name": metadata.get("class_name"),
            "kind": metadata.get("kind"),
            "hash_content": metadata.get("hash_content"),
            "role": metadata.get("role"),
            "task": metadata.get("task"),
            "rules": metadata.get("rules") or [],
            "examples": metadata.get("examples") or [],
            "config": metadata.get("config"),
            "input_schema": nodes_by_key.get(edge.get("from")),
            "output_schema": nodes_by_key.get(edge.get("to")),
            "forward_in_overridden": bool(metadata.get("forward_in_overridden")),
            "forward_out_overridden": bool(metadata.get("forward_out_overridden")),
            "trainable_paths": metadata.get("trainable_paths") or [],
            "langfuse_search_url": (
                f"{langfuse_base}/traces?search={quote(path)}" if langfuse_base else None
            ),
        }
    )


@router.get("/runs/{run_id}/agent/{path:path}/invocations")
async def agent_invocations(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    if not _events_for_path(ctx.events, path):
        return _not_found("unknown agent_path")
    langfuse_url = getattr(request.app.state, "langfuse_url", None)
    invocations = _build_invocations(
        run_id=run_id,
        events=ctx.events,
        agent_path=path,
        langfuse_url=langfuse_url,
    )
    return JSONResponse({"agent_path": path, "invocations": [inv.row for inv in invocations]})


@router.post("/runs/{run_id}/agent/{path:path}/invoke")
async def agent_invoke(request: Request, run_id: str, path: str) -> JSONResponse:
    if not bool(getattr(request.app.state, "allow_experiment", False)):
        return _error(403, "experiment endpoint disabled", code="experiment_disabled")

    try:
        body = _InvokeBody.model_validate(await request.json())
    except ValidationError as exc:
        return _error(400, f"invalid request body: {exc}", code="bad_request")

    resolver = getattr(request.app.state, "experiment_resolver", None)
    if resolver is None:
        return _error(
            409,
            "experiment resolver is not configured for this dashboard process",
            code="experiment_unavailable",
        )

    resolved = resolver(run_id, path)
    if resolved is None:
        return _error(
            409,
            "no live in-process agent found for this run_id/agent_path",
            code="experiment_unavailable",
        )

    log_path = Path(getattr(request.app.state, "experiment_log_path"))
    start_wall = time.time()
    log_base = {
        "ts": start_wall,
        "kind": "invoke",
        "run_id": run_id,
        "agent_path": path,
        "stream": bool(body.stream),
    }

    try:
        agent = resolved.clone()
        _apply_overrides(agent, body.overrides)
        x = agent.input.model_validate(body.input)
    except (ValidationError, ValueError) as exc:
        await asyncio.to_thread(
            _append_experiment_log,
            log_path,
            {**log_base, "status": "invalid", "error": str(exc)},
        )
        return _error(400, f"input/override validation failed: {exc}", code="bad_request")
    except Exception as exc:
        await asyncio.to_thread(
            _append_experiment_log,
            log_path,
            {**log_base, "status": "resolver_error", "error": str(exc)},
        )
        return _error(409, f"failed to prepare experiment agent: {exc}", code="experiment_unavailable")

    try:
        await agent.abuild()
        with suppress_notifications():
            envelope = await agent.invoke(x)
    except Exception as exc:
        await asyncio.to_thread(
            _append_experiment_log,
            log_path,
            {**log_base, "status": "error", "error": str(exc)},
        )
        return _error(500, f"experiment invoke failed: {exc}", code="invoke_failed")

    payload = envelope.model_dump(mode="json")
    metadata = {
        "experiment": True,
        "hash_content": agent.hash_content,
        "agent_path": path,
        "run_id": run_id,
    }
    payload["metadata"] = metadata

    await asyncio.to_thread(
        _append_experiment_log,
        log_path,
        {
            **log_base,
            "status": "ok",
            "latency_ms": payload.get("latency_ms"),
            "hash_prompt": payload.get("hash_prompt"),
            "hash_content": metadata["hash_content"],
        },
    )
    return JSONResponse(payload)


@router.get("/runs/{run_id}/agent/{path:path}/prompts")
async def agent_prompts(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    if not _events_for_path(ctx.events, path):
        return _not_found("unknown agent_path")
    cache_key = (run_id, path, float(ctx.summary.get("last_event_at") or 0.0))
    cached = _prompt_cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    langfuse_url = getattr(request.app.state, "langfuse_url", None)
    invocations = _build_invocations(
        run_id=run_id,
        events=ctx.events,
        agent_path=path,
        langfuse_url=langfuse_url,
    )
    renderer = "xml"
    entries: list[dict[str, Any]] = []
    for inv in invocations:
        meta = inv.terminal.get("metadata")
        meta = meta if isinstance(meta, dict) else {}
        config = meta.get("config")
        if isinstance(config, dict):
            io_cfg = config.get("io")
            if isinstance(io_cfg, dict) and isinstance(io_cfg.get("renderer"), str):
                renderer = io_cfg["renderer"]
        system = meta.get("prompt_system")
        user = meta.get("prompt_user")
        entries.append(
            {
                "invocation_id": inv.row["id"],
                "started_at": inv.row["started_at"],
                "hash_prompt": inv.row["hash_prompt"],
                "system": system if isinstance(system, str) else None,
                "user": user if isinstance(user, str) else None,
                "replayed": isinstance(system, str) and isinstance(user, str),
            }
        )
    payload = {"agent_path": path, "renderer": renderer, "entries": entries}
    _prompt_cache_set(cache_key, payload)
    return JSONResponse(payload)


@router.get("/runs/{run_id}/agent/{path:path}/values")
async def agent_values(
    request: Request,
    run_id: str,
    path: str,
    attr: str,
    side: str = "in",
) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    if side not in {"in", "out"}:
        return _not_found("side must be 'in' or 'out'")
    if not _events_for_path(ctx.events, path):
        return _not_found("unknown agent_path")

    invocations = _build_invocations(
        run_id=run_id,
        events=ctx.events,
        agent_path=path,
        langfuse_url=None,
    )
    values: list[dict[str, Any]] = []
    value_type = "unknown"
    for inv in invocations:
        source: Any = None
        if side == "in":
            source = inv.start.get("input") if inv.start is not None else None
        else:
            out = inv.terminal.get("output")
            if isinstance(out, dict) and isinstance(out.get("response"), dict):
                source = out["response"]
            elif isinstance(out, dict):
                source = out
        if not isinstance(source, dict):
            continue
        ok, value = _extract_attr(source, attr)
        if not ok:
            continue
        value_type = _value_type_name(value)
        values.append(
            {
                "invocation_id": inv.row["id"],
                "started_at": inv.row["started_at"],
                "value": value,
            }
        )
    if not values:
        return _not_found("unknown attribute for selected side")
    return JSONResponse(
        {
            "agent_path": path,
            "attribute": attr,
            "side": side,
            "type": value_type,
            "values": values,
        }
    )


@router.get("/runs/{run_id}/agent/{path:path}/events")
async def agent_events(
    request: Request,
    run_id: str,
    path: str,
    limit: int = _DEFAULT_EVENT_LIMIT,
) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    filtered = _events_for_path(ctx.events, path)
    if not filtered:
        return _not_found("unknown agent_path")
    safe_limit = max(1, min(limit, _MAX_EVENT_LIMIT))
    return JSONResponse({"run_id": run_id, "events": filtered[-safe_limit:]})


__all__ = ["router"]
