"""`OperadOutput` — the typed envelope returned by every `Agent.invoke`.

Wraps the user's declared `Out` with reproducibility (`hash_*`) and run
metadata (`run_id`, `agent_path`, timings, optional token/cost usage).
The `hash_*` cluster is SHA-256 truncated to 16 hex chars over a stable
JSON dump — for correlation and audit, not cryptographic integrity.

Hash helpers themselves live in ``operad.utils.hashing``; this module
keeps only the envelope type and the per-run state needed to thread
`hash_graph` through nested invocations.
"""

from __future__ import annotations

import platform
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from ..utils.hashing import hash_str


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
    "OPERAD_VERSION_HASH",
    "OperadOutput",
    "PYTHON_VERSION_HASH",
    "_RUN_GRAPH_HASH",
]
