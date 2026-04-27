"""Runtime primitives: concurrency slots, streaming, traces, observers.

Names like ``Trace``, ``ChunkEvent``, ``trace_diff`` are reachable via
their submodules (``operad.runtime.trace``, ``operad.runtime.streaming``,
``operad.runtime.trace_diff``). They are deliberately not re-exported
here to keep this package lazy — eager loading pulls in ``core``, which
would produce a circular import during ``operad.core.agent`` init.
"""

from __future__ import annotations

from .slots import SlotOccupancy, SlotRegistry, acquire, registry, set_limit

__all__ = [
    "SlotOccupancy",
    "SlotRegistry",
    "acquire",
    "registry",
    "set_limit",
]
