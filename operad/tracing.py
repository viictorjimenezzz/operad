"""One-liner tracing visibility.

Usage::

    import operad.tracing as tracing

    with tracing.watch(jsonl="run.jsonl"):
        out = await agent(x)

Module-level side effects, both opt-in via env var:

* ``OPERAD_TRACE=<path>`` registers a :class:`JsonlObserver` writing
  every event to that file.
* ``OPERAD_OTEL=1`` registers an :class:`OtelObserver` so spans flow to
  whatever OTLP endpoint the standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` /
  ``OTEL_EXPORTER_OTLP_HEADERS`` env vars point at (e.g. a self-hosted
  Langfuse). Requires the ``[otel]`` extra; if the deps are missing,
  the registration emits a warning and skips silently.

The Rich TUI is never attached automatically — keep explicit control
over terminal output via ``watch(rich=True)``.
"""

from __future__ import annotations

import os
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .runtime.cost import CostObserver
from .runtime.observers import JsonlObserver, registry


@contextmanager
def watch(
    *,
    jsonl: str | Path | None = None,
    rich: bool = True,
    cost: bool = False,
) -> Iterator[CostObserver | None]:
    """Attach default observers for the duration of the block.

    Parameters
    ----------
    jsonl:
        When set, append every :class:`AgentEvent` to this NDJSON file.
    rich:
        When true and the ``rich`` extra is installed, show a live TUI
        tree of in-flight agents. Degrades to a warning + no TUI when
        ``rich`` is missing.
    cost:
        When true, attach a :class:`CostObserver` that accumulates token
        and USD spend per ``run_id``. The observer is yielded so callers
        can read ``.totals()`` from inside the block.
    """
    added: list[object] = []

    if jsonl is not None:
        obs = JsonlObserver(jsonl)
        registry.register(obs)
        added.append(obs)

    cost_obs: CostObserver | None = None
    if cost:
        cost_obs = CostObserver()
        registry.register(cost_obs)
        added.append(cost_obs)

    rich_obs = None
    if rich:
        try:
            from .runtime.observers import RichDashboardObserver

            rich_obs = RichDashboardObserver()
        except ImportError:
            warnings.warn(
                "operad.tracing.watch(rich=True) requires the `observers` "
                "extra; continuing without the Rich TUI.",
                stacklevel=2,
            )
        else:
            registry.register(rich_obs)
            added.append(rich_obs)

    try:
        yield cost_obs
    finally:
        for obs in added:
            registry.unregister(obs)  # type: ignore[arg-type]
        if rich_obs is not None:
            rich_obs.stop()


if (_path := os.environ.get("OPERAD_TRACE")):
    registry.register(JsonlObserver(_path))


def _otel_env_truthy() -> bool:
    val = os.environ.get("OPERAD_OTEL", "")
    return val.lower() in ("1", "true", "yes", "on")


if _otel_env_truthy():
    try:
        from .runtime.observers import OtelObserver

        registry.register(OtelObserver())
    except (ImportError, RuntimeError) as exc:
        warnings.warn(
            f"OPERAD_OTEL=1 is set but OtelObserver could not be installed "
            f"({exc}). Install the `[otel]` extra to enable OTLP export.",
            stacklevel=2,
        )
