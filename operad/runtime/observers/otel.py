"""OpenTelemetry observer stub.

Kept as a seam: no hard OTel dependency. Fill in when we take one.
"""

from __future__ import annotations

from .base import AgentEvent


class OtelObserver:
    async def on_event(self, event: AgentEvent) -> None:
        # TODO: emit OTel spans when we take the OTel dependency.
        return None
