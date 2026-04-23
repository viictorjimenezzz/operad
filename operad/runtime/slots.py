"""Per-endpoint concurrency slots.

Local LLM servers (llama-server, LM Studio, Ollama) have finite parallel
capacity; unbounded `asyncio.gather` over agents pointing at the same
endpoint melts them. `SlotRegistry` hands out an `asyncio.Semaphore` per
`(backend, host)` pair so the default `Agent.forward` can acquire a slot
before calling `strands.invoke_async`.

Semaphores are lazily created. The global registry lives in `registry` and
is exposed through `acquire(cfg)` / `set_limit(...)`. An `asyncio.Semaphore`
is tied to the loop it was first used on, so each registry instance is
single-event-loop by convention (consistent with strands itself).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..core.config import Backend, Configuration


class SlotRegistry:
    """Semaphore pool keyed by `(backend, host)`.

    Attributes:
        default: Default slot count for endpoints without an explicit limit.
    """

    def __init__(self, default: int = 4) -> None:
        self.default = default
        self._limits: dict[tuple[Backend, str], int] = {}
        self._semaphores: dict[tuple[Backend, str], asyncio.Semaphore] = {}

    @staticmethod
    def _key(cfg: Configuration) -> tuple[Backend, str]:
        return (cfg.backend, cfg.host or "default")

    def set_limit(
        self,
        *,
        backend: Backend,
        host: str | None = None,
        limit: int,
    ) -> None:
        """Set the concurrency limit for a given endpoint.

        Must be called before the first `acquire` for that endpoint; changing
        an already-created semaphore is not supported (it would race with
        in-flight calls).
        """
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        key = (backend, host or "default")
        if key in self._semaphores:
            raise RuntimeError(
                f"semaphore for {key} already in use; set limits before build()"
            )
        self._limits[key] = limit

    def set_default(self, default: int) -> None:
        """Change the default slot count. Does not touch existing semaphores."""
        if default < 1:
            raise ValueError(f"default must be >= 1, got {default}")
        self.default = default

    def semaphore_for(self, cfg: Configuration) -> asyncio.Semaphore:
        key = self._key(cfg)
        sem = self._semaphores.get(key)
        if sem is None:
            sem = asyncio.Semaphore(self._limits.get(key, self.default))
            self._semaphores[key] = sem
        return sem

    def reset(self) -> None:
        """Drop every cached semaphore and limit (useful in tests)."""
        self._limits.clear()
        self._semaphores.clear()


registry = SlotRegistry()


def set_limit(
    *,
    backend: Backend,
    host: str | None = None,
    limit: int,
) -> None:
    """Configure concurrency for an endpoint on the default registry."""
    registry.set_limit(backend=backend, host=host, limit=limit)


@asynccontextmanager
async def acquire(cfg: Configuration) -> AsyncIterator[None]:
    """Acquire the slot for this configuration's endpoint for the duration."""
    sem = registry.semaphore_for(cfg)
    async with sem:
        yield
