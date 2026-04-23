"""`OperadOutput[Out]`: the canonical return envelope for every agent call.

Wraps the user's typed `response` with reproducibility hashes (`hash_*`),
run correlation (`run_id`, `agent_path`), timing, and optional usage.
`Agent.invoke` / `__call__` constructs one of these at the top of every
invocation; composites still pass plain `Out` through `forward`, so
double-wrapping is structurally impossible.

The `hash_*` cluster uses a stable-JSON SHA-256 truncated to 16 hex
chars. This is for display and correlation, not cryptographic use.
Inputs to the hash are always sorted-key JSON dumps of Pydantic
`model_dump` / `model_json_schema` output, so the same logical object
hashes identically across processes and Python versions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from .config import Configuration

Out = TypeVar("Out", bound=BaseModel)


def _stable_hash(obj: Any) -> str:
    """SHA-256 of sorted-key JSON, truncated to 16 hex chars.

    Display / correlation only — never use as a cryptographic primitive.
    Pydantic models should be dumped before being passed in; plain
    Python containers of primitives serialise directly.
    """
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def hash_configuration(cfg: Configuration) -> str:
    """Stable hash of a `Configuration`, excluding the `api_key` secret."""
    return _stable_hash(cfg.model_dump(mode="json", exclude={"api_key"}))


def hash_output_schema(output_model: type[BaseModel]) -> str:
    return _stable_hash(output_model.model_json_schema())


def hash_input(x: BaseModel) -> str:
    return _stable_hash(x.model_dump(mode="json"))


def hash_prompt(system: str, user: str) -> str:
    return _stable_hash({"system": system, "user": user})


def hash_graph(graph: Any) -> str:
    """Stable hash of an `AgentGraph`. Types (class objects) are folded
    to their qualified name so the result survives process boundaries.
    """

    def _node(n: Any) -> dict[str, Any]:
        d = asdict(n) if is_dataclass(n) else dict(n)
        for k in ("input_type", "output_type"):
            t = d.get(k)
            if isinstance(t, type):
                d[k] = f"{t.__module__}.{t.__qualname__}"
        return d

    return _stable_hash(
        {
            "root": getattr(graph, "root", None),
            "nodes": [_node(n) for n in getattr(graph, "nodes", [])],
            "edges": [_node(e) for e in getattr(graph, "edges", [])],
        }
    )


def _extract_usage(result: Any) -> dict[str, int] | None:
    """Best-effort usage extraction from a strands result object.

    Strands surfaces token counts on `result.metrics` in recent
    versions; older shapes nest them under `result.response.usage`.
    Returns `None` if nothing recognisable is present — callers treat
    that as "usage not available" and leave envelope fields as `None`.
    """
    metrics = getattr(result, "metrics", None)
    usage = None
    if metrics is not None:
        usage = getattr(metrics, "accumulated_usage", None) or getattr(
            metrics, "usage", None
        )
    if usage is None:
        response = getattr(result, "response", None)
        usage = getattr(response, "usage", None) if response is not None else None
    if usage is None:
        return None

    def _get(obj: Any, *names: str) -> int | None:
        for name in names:
            v = getattr(obj, name, None) if not isinstance(obj, dict) else obj.get(name)
            if isinstance(v, int):
                return v
        return None

    prompt = _get(usage, "inputTokens", "input_tokens", "prompt_tokens")
    completion = _get(
        usage, "outputTokens", "output_tokens", "completion_tokens"
    )
    if prompt is None and completion is None:
        return None
    out: dict[str, int] = {}
    if prompt is not None:
        out["prompt_tokens"] = prompt
    if completion is not None:
        out["completion_tokens"] = completion
    return out


class OperadOutput(BaseModel, Generic[Out]):
    """Typed envelope returned by every `Agent.invoke` / `__call__`.

    `response` carries the user's `Out`. The `hash_*` cluster fixes a
    reproducibility fingerprint of the run's inputs (model config,
    prompt, graph, payload, output schema) and of the library versions.
    Run metadata (`run_id`, `agent_path`, timings) mirrors the
    observer event for the same call. Usage fields populate when the
    backend exposes token counts; composites that never contact a model
    leave them `None`.
    """

    response: Out

    # Reproducibility — keep these contiguous for readability; pydantic
    # preserves declaration order in `model_dump` / JSON output.
    hash_operad_version: str
    hash_python_version: str
    hash_model: str
    hash_prompt: str
    hash_graph: str
    hash_input: str
    hash_output_schema: str

    # Run metadata
    run_id: str
    agent_path: str
    started_at: float
    finished_at: float
    latency_ms: float

    # Usage (optional; populated when the backend exposes it)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None


__all__ = [
    "OperadOutput",
    "_extract_usage",
    "_stable_hash",
    "hash_configuration",
    "hash_graph",
    "hash_input",
    "hash_output_schema",
    "hash_prompt",
]
