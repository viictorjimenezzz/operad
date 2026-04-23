"""Generic exponential-backoff retry helper for runtime calls.

Used by `Agent.forward` to wrap the provider call. Build-time code
paths must not retry — this helper is runtime-only.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import ValidationError

from ..utils.errors import BuildError

T = TypeVar("T")


_NON_RETRIABLE: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    BuildError,
    ValidationError,
)


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    backoff_base: float,
    timeout: float | None,
    on_attempt: Callable[[int, BaseException | None], None] | None = None,
) -> T:
    """Run ``fn`` with exponential-backoff retry and optional per-attempt timeout.

    ``max_retries=0`` runs a single attempt. ``max_retries=N`` permits up
    to ``N+1`` total attempts. The delay before retry ``i`` (1-indexed)
    is ``backoff_base * 2**(i-1) + uniform(0, backoff_base)``; jitter
    avoids synchronized retry storms across sibling agents.

    ``on_attempt(attempt_number, last_exception)`` fires at the start of
    every attempt so the caller can thread retry counts through a
    mutable dict without this helper knowing about observers.

    Non-transient failures (`BuildError`, `asyncio.CancelledError`,
    `pydantic.ValidationError`) re-raise immediately.
    """
    last: BaseException | None = None
    total = max_retries + 1
    for i in range(total):
        attempt = i + 1
        if on_attempt is not None:
            on_attempt(attempt, last)
        try:
            if timeout is None:
                return await fn()
            return await asyncio.wait_for(fn(), timeout=timeout)
        except _NON_RETRIABLE:
            raise
        except Exception as e:
            last = e
            if attempt == total:
                raise
            delay = backoff_base * (2 ** i) + random.uniform(0, backoff_base)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover
