"""Runtime primitives: concurrency slots, streaming, traces, observers.

Names like ``Trace``, ``ChunkEvent``, ``trace_diff`` are reachable via
their submodules (``operad.runtime.trace``, ``operad.runtime.streaming``,
``operad.runtime.trace_diff``). They are deliberately not re-exported
here to keep this package lazy — eager loading pulls in ``core``, which
would produce a circular import during ``operad.core.agent`` init.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .slots import SlotOccupancy, SlotRegistry, acquire, registry, set_limit

if TYPE_CHECKING:
    from .cost import CostObserver

__all__ = [
    "CostObserver",
    "SlotOccupancy",
    "SlotRegistry",
    "acquire",
    "registry",
    "set_limit",
]


def __getattr__(name: str) -> Any:
    if name == "CostObserver":
        from .cost import CostObserver as _CostObserver

        return _CostObserver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
