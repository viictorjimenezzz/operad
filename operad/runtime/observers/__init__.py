"""Observer protocol and built-in observers.

Observers receive `AgentEvent`s emitted by `Agent.invoke` via the
process-wide `registry`. Build-time tracing does not emit events.
"""

from __future__ import annotations

from .base import AgentEvent, Observer, ObserverRegistry, registry
from .jsonl import JsonlObserver
from .otel import OtelObserver
from .rich import RichDashboardObserver

__all__ = [
    "AgentEvent",
    "JsonlObserver",
    "Observer",
    "ObserverRegistry",
    "OtelObserver",
    "RichDashboardObserver",
    "registry",
]
