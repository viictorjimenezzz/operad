"""Per-agent dashboard endpoints used by the agent-detail view."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from operad.core.diff import diff_states
from operad.core.graph import TypeRegistry, from_json, to_io_graph
from operad.core.state import AgentState

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


def _invocation_id_map(
    *,
    run_id: str,
    events: list[dict[str, Any]],
    agent_path: str,
    langfuse_url: str | None = None,
) -> dict[str, _Invocation]:
    invocations = _build_invocations(
        run_id=run_id,
        events=events,
        agent_path=agent_path,
        langfuse_url=langfuse_url,
    )
    return {str(inv.row.get("id") or ""): inv for inv in invocations}


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
            "forward_in_doc": metadata.get("forward_in_doc"),
            "forward_out_doc": metadata.get("forward_out_doc"),
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


@router.get("/runs/{run_id}/agent/{path:path}/parameters")
async def agent_parameters(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    metadata = _latest_terminal_metadata(ctx.events, path)
    if metadata is None:
        return _not_found("unknown agent_path")
    raw = metadata.get("parameters")
    if not isinstance(raw, list):
        return JSONResponse({"agent_path": path, "parameters": []})
    params = [
        entry
        for entry in raw
        if isinstance(entry, dict) and bool(entry.get("requires_grad"))
    ]
    return JSONResponse({"agent_path": path, "parameters": params})


@router.get("/runs/{run_id}/agent/{path:path}/diff")
async def agent_diff(
    request: Request,
    run_id: str,
    path: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    if not from_ or not to:
        return _not_found("from/to invocation ids are required")
    if not _events_for_path(ctx.events, path):
        return _not_found("unknown agent_path")
    invocations = _invocation_id_map(
        run_id=run_id,
        events=ctx.events,
        agent_path=path,
        langfuse_url=None,
    )
    left = invocations.get(from_)
    right = invocations.get(to)
    if left is None or right is None:
        return _not_found("unknown invocation id(s)")

    left_meta = left.terminal.get("metadata")
    right_meta = right.terminal.get("metadata")
    left_meta = left_meta if isinstance(left_meta, dict) else {}
    right_meta = right_meta if isinstance(right_meta, dict) else {}
    left_snapshot = left_meta.get("state_snapshot")
    right_snapshot = right_meta.get("state_snapshot")
    if not isinstance(left_snapshot, dict) or not isinstance(right_snapshot, dict):
        return _not_found("state snapshots unavailable for one or both invocations")
    try:
        left_state = AgentState.model_validate(left_snapshot)
        right_state = AgentState.model_validate(right_snapshot)
    except Exception:
        return _not_found("state snapshots unavailable for one or both invocations")

    diff = diff_states(left_state, right_state)
    return JSONResponse(
        {
            "from_invocation": from_,
            "to_invocation": to,
            "from_hash_content": left_meta.get("hash_content"),
            "to_hash_content": right_meta.get("hash_content"),
            "changes": [
                {"path": c.path, "kind": c.kind, "detail": c.detail}
                for c in diff.changes
            ],
        }
    )


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
