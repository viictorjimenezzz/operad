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

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from operad.core.config import Configuration
from operad.core.agent import Example
from operad.core.diff import diff_states
from operad.core.view import to_agent_graph_from_json, to_io_graph_from_json
from operad.core.state import AgentState
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
    payload = to_io_graph_from_json(graph_json)
    return _enrich_io_graph_with_events(payload, ctx.events)


def _enrich_io_graph_with_events(
    payload: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Backfill ``class_name`` on edges using terminal event metadata.

    The graph snapshot is captured at root-build time, before sub-agent
    classes are necessarily resolvable; the event metadata always reflects
    the *runtime* class. This makes the rendered graph match what actually
    ran instead of the path-tail fallback.
    """
    runtime_class: dict[str, str] = {}
    for env in events:
        if env.get("type") != "agent_event" or env.get("kind") != "end":
            continue
        path = env.get("agent_path")
        if not isinstance(path, str):
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        cls = meta.get("class_name")
        if isinstance(cls, str) and cls:
            runtime_class.setdefault(path, cls)
    edges = payload.get("edges") or []
    for edge in edges:
        rt = runtime_class.get(edge.get("agent_path"))
        if rt:
            edge["class_name"] = rt
    payload["edges"] = edges
    return payload


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
        cfg = metadata.get("config") if isinstance(metadata.get("config"), dict) else {}
        cfg_io = cfg.get("io") if isinstance(cfg, dict) else None
        renderer = (
            cfg_io.get("renderer")
            if isinstance(cfg_io, dict) and isinstance(cfg_io.get("renderer"), str)
            else None
        )
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
                    "hash_model": output.get("hash_model"),
                    "hash_graph": output.get("hash_graph"),
                    "hash_output_schema": output.get("hash_output_schema"),
                    "hash_config": output.get("hash_config"),
                    "status": "ok" if kind == "end" else "error",
                    "error": None if kind == "end" else _error_repr(env),
                    "langfuse_url": (
                        f"{langfuse_url}/trace/{run_id}" if langfuse_url is not None else None
                    ),
                    "script": script,
                    "backend": (
                        output.get("backend")
                        or (cfg.get("backend") if isinstance(cfg, dict) else None)
                    ),
                    "model": (
                        output.get("model")
                        or (cfg.get("model") if isinstance(cfg, dict) else None)
                    ),
                    "renderer": renderer,
                    "input": start.get("input") if isinstance(start, dict) else None,
                    "output": output.get("response"),
                },
                start=start,
                terminal=env,
            )
        )
    return out


def _latest_terminal_envelope(events: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    for env in reversed(events):
        if env.get("type") != "agent_event":
            continue
        if env.get("agent_path") != path:
            continue
        if env.get("kind") != "end":
            continue
        return env
    return None


def _latest_terminal_metadata(events: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    env = _latest_terminal_envelope(events, path)
    if env is None:
        return None
    metadata = env.get("metadata")
    return metadata if isinstance(metadata, dict) else None


def _event_timestamp(env: dict[str, Any]) -> float:
    finished = env.get("finished_at")
    if isinstance(finished, (int, float)):
        return float(finished)
    started = env.get("started_at")
    if isinstance(started, (int, float)):
        return float(started)
    return 0.0


def _severity_label(value: Any) -> str | None:
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"low", "medium", "high"}:
            return lowered
        return None
    if isinstance(value, (int, float)):
        score = float(value)
        if score < 0.34:
            return "low"
        if score < 0.67:
            return "medium"
        return "high"
    return None


def _normalize_tape_link(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    mapping = {
        "epoch": "epoch",
        "batch": "batch",
        "iter": "iter",
        "optimizer_step": "optimizer_step",
        "optimizerStep": "optimizer_step",
    }
    for source_key, target_key in mapping.items():
        value = raw.get(source_key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            out[target_key] = value
            continue
        if isinstance(value, float):
            out[target_key] = int(value)
    return out or None


def _normalize_gradient(raw: Any, *, default_target: str | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    message = raw.get("message")
    severity = _severity_label(raw.get("severity"))
    target_paths = raw.get("target_paths")
    targets: list[str] = []
    if isinstance(target_paths, list):
        targets = [item for item in target_paths if isinstance(item, str) and item]
    if not targets and default_target is not None:
        targets = [default_target]
    if not isinstance(message, str):
        message = ""
    if severity is None:
        return None
    return {
        "message": message,
        "severity": severity,
        "target_paths": targets,
    }


def _path_matches(target: str, candidate: str) -> bool:
    if target == candidate:
        return True
    if target.endswith(f".{candidate}") or candidate.endswith(f".{target}"):
        return True
    return False


def _gradient_targets(payload: dict[str, Any]) -> list[str]:
    targets = payload.get("target_paths")
    if isinstance(targets, list):
        return [item for item in targets if isinstance(item, str) and item]
    by_field = payload.get("by_field")
    if isinstance(by_field, dict):
        return [str(key) for key in by_field.keys() if isinstance(key, str) and key]
    return []


def _latest_gradient_event_for_param(
    *,
    events: list[dict[str, Any]],
    param_path: str,
    before_ts: float | None,
) -> dict[str, Any] | None:
    for env in reversed(events):
        if env.get("type") != "algo_event":
            continue
        if env.get("kind") != "gradient_applied":
            continue
        timestamp = _event_timestamp(env)
        if before_ts is not None and timestamp > before_ts:
            continue
        payload = env.get("payload")
        if not isinstance(payload, dict):
            continue
        targets = _gradient_targets(payload)
        if any(_path_matches(param_path, candidate) for candidate in targets):
            return env
    return None


def _value_for_path(values: dict[str, Any], requested_path: str) -> tuple[str, Any] | None:
    if requested_path in values:
        return requested_path, values[requested_path]
    tail = requested_path.rsplit(".", 1)[-1]
    if tail in values:
        return tail, values[tail]
    for key, value in values.items():
        if not isinstance(key, str):
            continue
        if _path_matches(requested_path, key):
            return key, value
    return None


def _parameter_type(value: Any) -> str:
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return "rule_list"
        if all(isinstance(item, dict) for item in value):
            return "example_list"
        return "categorical"
    if isinstance(value, bool):
        return "categorical"
    if isinstance(value, (int, float)):
        return "float"
    if isinstance(value, dict):
        return "configuration"
    return "categorical"


def _short_hash(value: Any) -> str:
    return uuid.uuid5(uuid.NAMESPACE_OID, repr(value)).hex[:16]


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


@router.get("/runs/{run_id}/agent_graph")
async def agent_graph(request: Request, run_id: str) -> JSONResponse:
    """Return the agent-flow graph: agents as nodes, types as edge labels."""
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
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
        return JSONResponse({"root": None, "nodes": [], "edges": []})
    payload = to_agent_graph_from_json(graph_json)

    # Backfill class_name on agents using runtime metadata from end events,
    # mirroring _enrich_io_graph_with_events.
    runtime_class: dict[str, str] = {}
    for env in ctx.events:
        if env.get("type") != "agent_event" or env.get("kind") != "end":
            continue
        path = env.get("agent_path")
        if not isinstance(path, str):
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        cls = meta.get("class_name")
        if isinstance(cls, str) and cls:
            runtime_class.setdefault(path, cls)
    for node in payload.get("nodes") or []:
        rt = runtime_class.get(node.get("path"))
        if rt:
            node["class_name"] = rt
    return JSONResponse(payload)


@router.get("/runs/{run_id}/invocations")
async def root_invocations(request: Request, run_id: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    root_path = _root_agent_path(ctx)
    if root_path is None:
        return JSONResponse({"agent_path": None, "invocations": []})
    langfuse_url = getattr(request.app.state, "langfuse_url", None)
    invocations = _build_invocations(
        run_id=run_id,
        events=ctx.events,
        agent_path=root_path,
        langfuse_url=langfuse_url,
    )
    fallback = _leaf_backend_fallback(ctx.events, root_path)
    rows: list[dict[str, Any]] = []
    for inv in invocations:
        row = inv.row
        if not row.get("backend") and fallback.get("backend"):
            row["backend"] = fallback["backend"]
        if not row.get("model") and fallback.get("model"):
            row["model"] = fallback["model"]
        if not row.get("renderer") and fallback.get("renderer"):
            row["renderer"] = fallback["renderer"]
        rows.append(row)
    return JSONResponse({"agent_path": root_path, "invocations": rows})


def _leaf_backend_fallback(
    events: list[dict[str, Any]],
    root_path: str,
) -> dict[str, str | None]:
    """Walk descendant-leaf end events to surface backend/model/renderer.

    Composite roots have ``config: None``; this fallback lets the
    dashboard badges show the actual model an agent invoked even when
    the user clicks the composite (which itself has no backend).
    """
    backend: str | None = None
    model: str | None = None
    renderer: str | None = None
    for env in events:
        if env.get("type") != "agent_event" or env.get("kind") != "end":
            continue
        path = env.get("agent_path")
        if not isinstance(path, str) or path == root_path:
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        cfg = meta.get("config")
        if not isinstance(cfg, dict):
            continue
        backend = backend or (cfg.get("backend") if isinstance(cfg.get("backend"), str) else None)
        model = model or (cfg.get("model") if isinstance(cfg.get("model"), str) else None)
        io = cfg.get("io") if isinstance(cfg.get("io"), dict) else None
        if isinstance(io, dict) and isinstance(io.get("renderer"), str):
            renderer = renderer or io["renderer"]
        if backend and model and renderer:
            break
    return {"backend": backend, "model": model, "renderer": renderer}


@router.get("/runs/{run_id}/agent/{path:path}/meta")
async def agent_meta(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    metadata = _latest_terminal_metadata(ctx.events, path)
    if metadata is None:
        return _not_found("unknown agent_path")
    io_graph = _io_graph_payload(ctx)
    edge = next((e for e in io_graph.get("edges", []) if e.get("agent_path") == path), None)
    nodes_by_key = {n.get("key"): n for n in io_graph.get("nodes", []) if isinstance(n, dict)}
    graph_json = ctx.graph_json or {}
    graph_nodes = [n for n in graph_json.get("nodes") or [] if isinstance(n, dict)]
    graph_node = next((n for n in graph_nodes if n.get("path") == path), None)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    if edge is not None:
        input_schema = nodes_by_key.get(edge.get("from"))
        output_schema = nodes_by_key.get(edge.get("to"))
    if graph_node is not None:
        if input_schema is None and graph_node.get("input"):
            input_schema = nodes_by_key.get(graph_node["input"]) or {
                "key": graph_node["input"],
                "name": str(graph_node["input"]).rsplit(".", 1)[-1],
                "fields": [
                    f for f in graph_node.get("input_fields") or [] if isinstance(f, dict)
                ],
            }
        if output_schema is None and graph_node.get("output"):
            output_schema = nodes_by_key.get(graph_node["output"]) or {
                "key": graph_node["output"],
                "name": str(graph_node["output"]).rsplit(".", 1)[-1],
                "fields": [
                    f for f in graph_node.get("output_fields") or [] if isinstance(f, dict)
                ],
            }
    kind = metadata.get("kind") or (graph_node.get("kind") if graph_node else None)
    if kind not in {"leaf", "composite"}:
        kind = "leaf" if edge is not None else "composite"
    langfuse_base = getattr(request.app.state, "langfuse_url", None)
    return JSONResponse(
        {
            "agent_path": path,
            "class_name": metadata.get("class_name"),
            "kind": kind,
            "hash_content": metadata.get("hash_content"),
            "role": metadata.get("role"),
            "task": metadata.get("task"),
            "rules": metadata.get("rules") or [],
            "examples": metadata.get("examples") or [],
            "config": metadata.get("config"),
            "input_schema": input_schema,
            "output_schema": output_schema,
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


@router.get("/runs/{run_id}/agent/{path:path}/parameters")
async def agent_parameters(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    terminal = _latest_terminal_envelope(ctx.events, path)
    if terminal is None:
        return _not_found("unknown agent_path")
    metadata = terminal.get("metadata")
    if not isinstance(metadata, dict):
        return _not_found("unknown agent_path")
    raw = metadata.get("parameters")
    if not isinstance(raw, list):
        return JSONResponse({"agent_path": path, "parameters": []})
    terminal_ts = _event_timestamp(terminal)
    params: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or not bool(entry.get("requires_grad")):
            continue
        param_path = entry.get("path")
        if not isinstance(param_path, str) or not param_path:
            continue
        gradient_event = _latest_gradient_event_for_param(
            events=ctx.events,
            param_path=param_path,
            before_ts=terminal_ts,
        )
        gradient = _normalize_gradient(entry.get("gradient") or entry.get("grad"), default_target=param_path)
        tape_link = _normalize_tape_link(entry.get("tape_link"))
        if gradient_event is not None:
            payload = gradient_event.get("payload")
            if isinstance(payload, dict):
                event_gradient = _normalize_gradient(payload, default_target=param_path)
                if event_gradient is not None:
                    gradient = event_gradient
                event_tape_link = _normalize_tape_link(payload)
                if event_tape_link is not None:
                    tape_link = event_tape_link
        params.append(
            {
                "requires_grad": True,
                "path": param_path,
                "value": entry.get("value"),
                "hash": entry.get("hash"),
                "tape_link": tape_link,
                "gradient": gradient,
            }
        )
    return JSONResponse({"agent_path": path, "parameters": params})


@router.get("/runs/{run_id}/parameter-evolution/{path:path}")
async def parameter_evolution(request: Request, run_id: str, path: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")

    lineage: list[RunInfo] = []
    if ctx.info is not None:
        root_path = ctx.info.root_agent_path
        root_hash: str | None = None
        if isinstance(root_path, str):
            root_env = _latest_terminal_envelope(ctx.info.events, root_path)
            if isinstance(root_env, dict):
                root_meta = root_env.get("metadata")
                if isinstance(root_meta, dict):
                    hash_content = root_meta.get("hash_content")
                    if isinstance(hash_content, str) and hash_content:
                        root_hash = hash_content
        if root_hash is not None:
            lineage = list(request.app.state.observer.registry.runs_by_hash_full(root_hash))
        if not lineage:
            lineage = [ctx.info]

    points: list[dict[str, Any]] = []
    inferred_type: str | None = None
    langfuse_base = getattr(request.app.state, "langfuse_url", None)
    requested_agent_path = path.rsplit(".", 1)[0] if "." in path else None
    for info in lineage:
        chosen_snapshot: dict[str, Any] | None = None
        matched_key: str | None = None
        value: Any = None
        for snapshot in reversed(info.parameter_snapshots):
            values = snapshot.get("values")
            if not isinstance(values, dict):
                continue
            snapshot_agent_path = snapshot.get("agent_path")
            if isinstance(snapshot_agent_path, str) and snapshot_agent_path:
                if requested_agent_path is not None and snapshot_agent_path != requested_agent_path:
                    continue
            match = _value_for_path(values, path)
            if match is None:
                continue
            matched_key, value = match
            chosen_snapshot = snapshot
            break
        if chosen_snapshot is None or matched_key is None:
            continue

        if inferred_type is None:
            inferred_type = _parameter_type(value)
        details = chosen_snapshot.get("details")
        detail = details.get(matched_key) if isinstance(details, dict) else None
        detail = detail if isinstance(detail, dict) else {}
        tape_link = _normalize_tape_link(detail.get("tape_link") or chosen_snapshot.get("tape_link"))
        gradient = _normalize_gradient(detail.get("gradient"), default_target=path)
        snapshot_ts = chosen_snapshot.get("timestamp")
        before_ts = float(snapshot_ts) if isinstance(snapshot_ts, (int, float)) else None
        gradient_event = _latest_gradient_event_for_param(
            events=list(info.events),
            param_path=path,
            before_ts=before_ts,
        )
        if gradient_event is not None:
            payload = gradient_event.get("payload")
            if isinstance(payload, dict):
                event_gradient = _normalize_gradient(payload, default_target=path)
                if event_gradient is not None:
                    gradient = event_gradient
                event_tape_link = _normalize_tape_link(payload)
                if event_tape_link is not None:
                    tape_link = event_tape_link

        metric_snapshot = info.metrics or None
        hash_value = detail.get("hash")
        if not isinstance(hash_value, str) or not hash_value:
            hash_value = _short_hash(value)

        points.append(
            {
                "run_id": info.run_id,
                "started_at": info.started_at,
                "value": value,
                "hash": hash_value,
                "gradient": gradient,
                "source_tape_step": tape_link,
                "langfuse_url": (
                    f"{langfuse_base}/trace/{info.run_id}" if isinstance(langfuse_base, str) else None
                ),
                "metric_snapshot": metric_snapshot,
            }
        )

    points.sort(key=lambda row: float(row.get("started_at") or 0.0))
    return JSONResponse(
        {
            "path": path,
            "type": inferred_type or "categorical",
            "points": points,
        }
    )


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


@router.get("/runs/by-hash")
async def runs_by_hash(request: Request, hash_content: str = Query(...)) -> JSONResponse:
    """Find runs whose root agent shares the given ``hash_content``.

    Used by the dashboard to surface "sister runs" — instances of the
    same Pipeline class with identical declared state. Walks the live
    registry and (when present) the archive store.
    """
    target = hash_content.strip()
    if not target:
        return JSONResponse({"matches": []})

    matches: list[dict[str, Any]] = []
    obs = request.app.state.observer
    try:
        live_runs = obs.registry.list()
    except Exception:
        live_runs = []
    for info in live_runs:
        try:
            last_hash = _latest_root_hash_content(info)
            summary = info.summary()
        except Exception:
            continue
        if last_hash and last_hash.startswith(target):
            matches.append(summary)

    store = getattr(request.app.state, "archive_store", None)
    if store is not None:
        # Best-effort scan; archive payloads include the same summaries.
        try:
            archived = store.list_runs(limit=200)
        except Exception:
            archived = []
        for entry in archived:
            summary = entry if isinstance(entry, dict) else None
            if summary is None:
                continue
            invocations = summary.get("invocations") or []
            if not isinstance(invocations, list):
                continue
            last = invocations[-1] if invocations else None
            if not isinstance(last, dict):
                continue
            hc = last.get("hash_content")
            if isinstance(hc, str) and hc.startswith(target):
                matches.append(summary)

    return JSONResponse({"matches": matches})


def _latest_root_hash_content(info: RunInfo) -> str | None:
    """Walk the run's events back-to-front to find the latest root agent
    end event, and return the hash_content from its metadata if present."""
    try:
        summary = info.summary()
    except Exception:
        return None
    root_path = summary.get("root_agent_path")
    if not isinstance(root_path, str):
        return None
    try:
        events = list(info.events)
    except Exception:
        return None
    for env in reversed(events):
        if env.get("type") != "agent_event":
            continue
        if env.get("kind") != "end":
            continue
        if env.get("agent_path") != root_path:
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        hc = meta.get("hash_content")
        if isinstance(hc, str):
            return hc
    return None


# ---------------------------------------------------------------------------
# Tab layout hint endpoint — backend can return a tailored JSON layout per
# tab (overview / graph / invocations) for any run. Frontend ships its own
# defaults and falls back when this endpoint 404s.
# ---------------------------------------------------------------------------


_DEFAULT_OVERVIEW_LAYOUT: dict[str, Any] = {
    "algorithm": "agent.overview",
    "version": 1,
    "dataSources": {
        "summary": {"endpoint": "/runs/$context.runId/summary"},
        "invocations": {"endpoint": "/runs/$context.runId/invocations"},
    },
    "spec": {
        "root": "page",
        "elements": {
            "page": {
                "type": "Stack",
                "props": {"gap": 16},
                "children": ["latest", "more", "sections"],
            },
            "latest": {
                "type": "LatestInvocationCard",
                "props": {
                    "sourceSummary": "$queries.summary",
                    "sourceInvocations": "$queries.invocations",
                    "runId": "$context.runId",
                },
            },
            "more": {
                "type": "InvocationsList",
                "props": {
                    "sourceSummary": "$queries.summary",
                    "sourceInvocations": "$queries.invocations",
                    "runId": "$context.runId",
                    "skipLatest": True,
                    "density": "compact",
                },
            },
            "sections": {
                "type": "Stack",
                "props": {"gap": 8},
                "children": [
                    "repro",
                    "backend",
                    "config",
                    "examples",
                    "drift",
                    "cost",
                    "trainable",
                    "sister",
                ],
            },
            "repro": {
                "type": "ReproducibilityBlock",
                "props": {"sourceInvocations": "$queries.invocations"},
            },
            "backend": {
                "type": "BackendBlock",
                "props": {
                    "sourceSummary": "$queries.summary",
                    "sourceInvocations": "$queries.invocations",
                    "runId": "$context.runId",
                },
            },
            "config": {
                "type": "ConfigBlock",
                "props": {"sourceSummary": "$queries.summary", "runId": "$context.runId"},
            },
            "examples": {
                "type": "ExamplesBlock",
                "props": {"sourceSummary": "$queries.summary", "runId": "$context.runId"},
            },
            "drift": {
                "type": "DriftBlock",
                "props": {
                    "sourceInvocations": "$queries.invocations",
                    "runId": "$context.runId",
                },
            },
            "cost": {
                "type": "CostLatencyBlock",
                "props": {"sourceInvocations": "$queries.invocations"},
            },
            "trainable": {
                "type": "TrainableParamsBlock",
                "props": {"sourceSummary": "$queries.summary", "runId": "$context.runId"},
            },
            "sister": {
                "type": "SisterRunsBlock",
                "props": {
                    "sourceInvocations": "$queries.invocations",
                    "runId": "$context.runId",
                },
            },
        },
    },
}


@router.get("/runs/{run_id}/layout/{tab}")
async def run_tab_layout(request: Request, run_id: str, tab: str) -> JSONResponse:
    ctx = _resolve_run_context(request, run_id)
    if ctx is None:
        return _not_found("unknown run_id")
    if tab == "overview":
        return JSONResponse(_DEFAULT_OVERVIEW_LAYOUT)
    return _not_found("no layout for tab")


__all__ = ["router"]
