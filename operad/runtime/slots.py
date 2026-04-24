"""Per-endpoint slots: concurrency + optional RPM / TPM gates.

Local LLM servers (llama-server, LM Studio, Ollama) have finite parallel
capacity; unbounded `asyncio.gather` over agents pointing at the same
endpoint melts them. Hosted providers (OpenAI, Anthropic) additionally
rate-limit on requests-per-minute (RPM) and tokens-per-minute (TPM) —
concurrency alone doesn't prevent a low-parallelism fleet from blowing
past those budgets.

`SlotRegistry` hands out per-`(backend, host)` gates: an
`asyncio.Semaphore` for concurrency, and two `SlidingCounter`s for RPM
and TPM. `acquire(cfg)` holds all three gates before yielding a
`SlotToken`; the caller `settle(tokens=...)` after the call completes
to reconcile the provisional TPM reserve against the actual token cost.

Loop affinity: `asyncio.Semaphore` and `asyncio.Future` are
loop-bound, so each registry is single-event-loop by convention
(consistent with strands itself). Multi-loop test harnesses must call
`registry.reset()` between loops.
"""

from __future__ import annotations

import asyncio
import collections
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from ..core.config import Backend, Configuration

_Key = tuple[Backend, str]

_WINDOW_SECONDS = 60.0


def _default_time() -> float:
    return asyncio.get_running_loop().time()


class SlidingCounter:
    """60-second sliding window over a single quantity (requests or tokens).

    `limit == 0` means unlimited (fast-path). Negative limits raise.
    Wakeups fire in FIFO order among waiters whose `need` fits.
    """

    def __init__(
        self,
        limit: int,
        *,
        time_fn: Callable[[], float] = _default_time,
    ) -> None:
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")
        self.limit = limit
        self._time_fn = time_fn
        self._events: collections.deque[tuple[float, int]] = collections.deque()
        self._waiters: collections.deque[tuple[int, asyncio.Future[None]]] = (
            collections.deque()
        )

    def set_limit(self, limit: int) -> None:
        if limit < 0:
            raise ValueError(f"limit must be >= 0, got {limit}")
        self.limit = limit
        self._wake()

    def _expire(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        ev = self._events
        while ev and ev[0][0] < cutoff:
            ev.popleft()

    def current(self, now: float | None = None) -> int:
        t = self._time_fn() if now is None else now
        self._expire(t)
        return sum(n for _, n in self._events)

    async def acquire(self, amount: int) -> None:
        if self.limit == 0 or amount <= 0:
            return
        now = self._time_fn()
        self._expire(now)
        if sum(n for _, n in self._events) + amount <= self.limit and not self._waiters:
            return
        fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append((amount, fut))
        try:
            await fut
        except BaseException:
            try:
                self._waiters.remove((amount, fut))
            except ValueError:
                pass
            raise

    def charge(self, amount: int, *, at: float | None = None) -> None:
        if self.limit == 0 or amount <= 0:
            return
        now = self._time_fn() if at is None else at
        self._expire(now)
        self._events.append((now, amount))
        self._wake()

    def refund(self, amount: int) -> None:
        """Remove `amount` from the most recent events (best-effort).

        Walks from newest to oldest, subtracting from each event until
        `amount` is consumed. Used to reconcile a provisional TPM
        reserve against the actual token count at `settle()`.
        """
        if self.limit == 0 or amount <= 0:
            return
        remaining = amount
        ev = self._events
        i = len(ev) - 1
        while remaining > 0 and i >= 0:
            ts, n = ev[i]
            take = min(n, remaining)
            new_n = n - take
            remaining -= take
            if new_n == 0:
                del ev[i]
            else:
                ev[i] = (ts, new_n)
            i -= 1
        self._wake()

    def _wake(self) -> None:
        if not self._waiters:
            return
        now = self._time_fn()
        self._expire(now)
        current = sum(n for _, n in self._events)
        while self._waiters:
            need, fut = self._waiters[0]
            if current + need > self.limit:
                break
            self._waiters.popleft()
            if not fut.done():
                fut.set_result(None)
            current += need


class SlotToken:
    """Handle returned by `acquire`; reconciles TPM reservation on settle."""

    __slots__ = ("_tpm", "_reserved", "_settled")

    def __init__(self, tpm: SlidingCounter | None, reserved: int) -> None:
        self._tpm = tpm
        self._reserved = reserved
        self._settled = False

    def settle(self, *, tokens: int) -> None:
        """Refund the provisional reserve and charge the actual cost.

        Idempotent: first call wins. Guards against retry paths
        double-billing. Callers on error paths should still invoke
        `settle(tokens=0)` so the reserve is released.
        """
        if self._settled:
            return
        self._settled = True
        if self._tpm is None:
            return
        if self._reserved:
            self._tpm.refund(self._reserved)
        if tokens > 0:
            self._tpm.charge(tokens)


class SlotRegistry:
    """Per-endpoint gates keyed by `(backend, host)`.

    Attributes:
        default: Default concurrency for endpoints without an explicit
            concurrency limit.
    """

    def __init__(self, default: int = 4) -> None:
        self.default = default
        self._concurrency: dict[_Key, int] = {}
        self._semaphores: dict[_Key, asyncio.Semaphore] = {}
        self._rpm_limits: dict[_Key, int] = {}
        self._tpm_limits: dict[_Key, int] = {}
        self._rpm: dict[_Key, SlidingCounter] = {}
        self._tpm: dict[_Key, SlidingCounter] = {}

    @staticmethod
    def _key(cfg: Configuration) -> _Key:
        return (cfg.backend, cfg.host or "default")

    def set_limit(
        self,
        *,
        backend: Backend,
        host: str | None = None,
        concurrency: int | None = None,
        rpm: int | None = None,
        tpm: int | None = None,
    ) -> None:
        """Configure per-endpoint caps.

        Any omitted field leaves the current value unchanged.
        `concurrency` may only be set before the first acquire on that
        endpoint (semaphore identity must stay stable). `rpm` and `tpm`
        may be updated at any time — they're sliding-window counters
        whose budget can change mid-flight. `0` means unlimited.
        """
        key = (backend, host or "default")
        if concurrency is not None:
            if concurrency < 1:
                raise ValueError(f"concurrency must be >= 1, got {concurrency}")
            if key in self._semaphores:
                raise RuntimeError(
                    f"semaphore for {key} already in use; set concurrency before build()"
                )
            self._concurrency[key] = concurrency
        if rpm is not None:
            if rpm < 0:
                raise ValueError(f"rpm must be >= 0, got {rpm}")
            self._rpm_limits[key] = rpm
            existing = self._rpm.get(key)
            if existing is None:
                self._rpm[key] = SlidingCounter(rpm)
            else:
                existing.set_limit(rpm)
        if tpm is not None:
            if tpm < 0:
                raise ValueError(f"tpm must be >= 0, got {tpm}")
            self._tpm_limits[key] = tpm
            existing = self._tpm.get(key)
            if existing is None:
                self._tpm[key] = SlidingCounter(tpm)
            else:
                existing.set_limit(tpm)

    def set_default(self, default: int) -> None:
        """Change the default concurrency. Does not touch existing semaphores."""
        if default < 1:
            raise ValueError(f"default must be >= 1, got {default}")
        self.default = default

    def semaphore_for(self, cfg: Configuration) -> asyncio.Semaphore:
        key = self._key(cfg)
        sem = self._semaphores.get(key)
        if sem is None:
            sem = asyncio.Semaphore(self._concurrency.get(key, self.default))
            self._semaphores[key] = sem
        return sem

    def rpm_for(self, cfg: Configuration) -> SlidingCounter | None:
        return self._rpm.get(self._key(cfg))

    def tpm_for(self, cfg: Configuration) -> SlidingCounter | None:
        return self._tpm.get(self._key(cfg))

    def reset(self) -> None:
        """Drop every cached gate (useful in tests)."""
        self._concurrency.clear()
        self._semaphores.clear()
        self._rpm_limits.clear()
        self._tpm_limits.clear()
        self._rpm.clear()
        self._tpm.clear()


registry = SlotRegistry()


def set_limit(
    *,
    backend: Backend,
    host: str | None = None,
    concurrency: int | None = None,
    rpm: int | None = None,
    tpm: int | None = None,
) -> None:
    """Configure per-endpoint caps on the default registry."""
    registry.set_limit(
        backend=backend,
        host=host,
        concurrency=concurrency,
        rpm=rpm,
        tpm=tpm,
    )


def _provisional_reserve(cfg: Configuration) -> int:
    # Over-estimate intentionally: undershoot would over-admit and
    # breach TPM. The real prompt length isn't available here (it's
    # formatted in `forward` before `acquire`), so use 2 × max_tokens
    # as a cheap conservative bound. `settle()` reconciles to truth.
    return max(1, 2 * cfg.max_tokens)


@asynccontextmanager
async def acquire(cfg: Configuration) -> AsyncIterator[SlotToken]:
    """Acquire all active gates for this config's endpoint.

    Order: concurrency (semaphore) → RPM → TPM. Yields a `SlotToken`;
    the caller must `settle(tokens=...)` after the call. The context
    manager's `finally` settles with `tokens=0` as a safety net so the
    provisional TPM reserve is always released even on error.
    """
    sem = registry.semaphore_for(cfg)
    async with sem:
        rpm = registry.rpm_for(cfg)
        if rpm is not None:
            await rpm.acquire(1)
            rpm.charge(1)
        tpm = registry.tpm_for(cfg)
        reserved = 0
        if tpm is not None:
            reserved = _provisional_reserve(cfg)
            await tpm.acquire(reserved)
            tpm.charge(reserved)
        token = SlotToken(tpm, reserved)
        try:
            yield token
        finally:
            token.settle(tokens=0)


__all__ = [
    "SlidingCounter",
    "SlotRegistry",
    "SlotToken",
    "acquire",
    "registry",
    "set_limit",
]
