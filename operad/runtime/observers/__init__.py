"""Observer protocol and built-in observers.

Observers receive `AgentEvent`s emitted by `Agent.invoke` and
`AlgorithmEvent`s emitted by algorithms via the process-wide `registry`.
Build-time tracing does not emit events.
"""

from __future__ import annotations

from ..events import AlgorithmEvent, AlgoKind
from .base import (
    AgentEvent,
    Event,
    Observer,
    ObserverRegistry,
    emit_algorithm_event,
    registry,
)
from .jsonl import JsonlObserver
from .otel import OtelObserver
from .rich import RichDashboardObserver

__all__ = [
    "AgentEvent",
    "AlgoKind",
    "AlgorithmEvent",
    "Event",
    "JsonlObserver",
    "Observer",
    "ObserverRegistry",
    "OtelObserver",
    "RichDashboardObserver",
    "emit_algorithm_event",
    "registry",
]
