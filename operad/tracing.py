"""One-liner tracing visibility.

Usage::

    import operad.tracing as tracing

    with tracing.watch(jsonl="run.jsonl"):
        out = await agent(x)

Module-level side effect: if the ``OPERAD_TRACE`` environment variable
is set at import time, a :class:`JsonlObserver` writing to that path is
registered on the process-wide observer registry. Unset the env-var (or
avoid importing this module) to opt out. The Rich TUI is never attached
automatically — keep explicit control over terminal output via
``watch(rich=True)``.
"""

from __future__ import annotations

import os
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .runtime.observers import JsonlObserver, registry


@contextmanager
def watch(
    *, jsonl: str | Path | None = None, rich: bool = True
) -> Iterator[None]:
    """Attach default observers for the duration of the block.

    Parameters
    ----------
    jsonl:
        When set, append every :class:`AgentEvent` to this NDJSON file.
    rich:
        When true and the ``rich`` extra is installed, show a live TUI
        tree of in-flight agents. Degrades to a warning + no TUI when
        ``rich`` is missing.
    """
    added: list[object] = []

    if jsonl is not None:
        obs = JsonlObserver(jsonl)
        registry.register(obs)
        added.append(obs)

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
        yield
    finally:
        for obs in added:
            registry.unregister(obs)  # type: ignore[arg-type]
        if rich_obs is not None:
            rich_obs.stop()


if (_path := os.environ.get("OPERAD_TRACE")):
    registry.register(JsonlObserver(_path))
