"""`OperadOutput` — the typed envelope returned by every `Agent.invoke`.

Wraps the user's declared `Out` with reproducibility (`hash_*`) and run
metadata (`run_id`, `agent_path`, timings, optional token/cost usage).
The `hash_*` cluster is SHA-256 truncated to 16 hex chars over a stable
JSON dump — for correlation and audit, not cryptographic integrity.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from .config import Configuration


Out = TypeVar("Out", bound=BaseModel)


class OperadOutput(BaseModel, Generic[Out]):
    """Envelope returned by every `Agent.invoke` call.

    `response` carries the user's typed output; the `hash_*` cluster
    captures reproducibility metadata; the remaining fields describe
    the run. Child invocations in a tree share the same `run_id` and
    `hash_graph` as the root call.
    """

    response: Out

    hash_operad_version: str = ""
    hash_python_version: str = ""
    hash_model: str = ""
    hash_prompt: str = ""
    hash_graph: str = ""
    hash_input: str = ""
    hash_output_schema: str = ""

    run_id: str = ""
    agent_path: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    latency_ms: float = 0.0

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- hash helpers -----------------------------------------------------------


def hash_str(s: str) -> str:
    """SHA-256 of `s`, truncated to 16 hex chars."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def hash_json(obj: Any) -> str:
    """Stable hash of a JSON-serialisable object."""
    return hash_str(json.dumps(obj, sort_keys=True, default=str))


# Matches a `user:pass@` authority prefix, with or without a leading scheme.
# Credentials embedded in `host` would otherwise be hashed verbatim, making
# identical deployments hash differently based on operator.
_HOST_AUTH_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.-]*://)?[^/@]+@")


def hash_config(config: Configuration | None) -> str:
    """Hash a `Configuration` with `api_key` excluded.

    The `host` field is additionally scrubbed of any embedded
    `user:pass@` authority so credentials never bleed into the
    reproducibility hash.
    """
    if config is None:
        return ""
    dumped = config.model_dump(mode="json", exclude={"api_key"})
    host = dumped.get("host")
    if isinstance(host, str):
        m = _HOST_AUTH_RE.match(host)
        if m:
            dumped["host"] = (m.group("scheme") or "") + host[m.end():]
    return hash_json(dumped)


def hash_schema(cls: type[BaseModel]) -> str:
    """Hash the JSON schema of a Pydantic model."""
    return hash_json(cls.model_json_schema())


def _operad_version() -> str:
    try:
        return _pkg_version("operad")
    except PackageNotFoundError:
        return "0.0.0+unknown"


OPERAD_VERSION_HASH = hash_str(_operad_version())
PYTHON_VERSION_HASH = hash_str(platform.python_version())


# Per-run context: every `OperadOutput` produced inside one root invocation
# carries the same `hash_graph` value. Set at the root's invoke entry.
_RUN_GRAPH_HASH: ContextVar[str] = ContextVar("_RUN_GRAPH_HASH", default="")


__all__ = [
    "OperadOutput",
    "OPERAD_VERSION_HASH",
    "PYTHON_VERSION_HASH",
    "_RUN_GRAPH_HASH",
    "hash_config",
    "hash_json",
    "hash_schema",
    "hash_str",
]
