"""Tests for the concurrency-slot registry."""

from __future__ import annotations
import asyncio
import pytest
from operad import Configuration
from operad.core.config import Sampling
from operad.runtime import SlotRegistry, acquire, registry
from operad.runtime.slots import SlidingCounter
import time


# --- from test_runtime_slots.py ---
pytestmark = pytest.mark.asyncio


def _cfg(host: str) -> Configuration:
    return Configuration(backend="llamacpp", host=host, model="m")


async def test_limit_1_serializes_two_concurrent_acquires() -> None:
    reg = SlotRegistry(default=4)
    reg.set_limit(backend="llamacpp", host="127.0.0.1:1", concurrency=1)
    order: list[str] = []

    async def worker(tag: str, hold: float) -> None:
        async with reg.semaphore_for(_cfg("127.0.0.1:1")):
            order.append(f"{tag}:enter")
            await asyncio.sleep(hold)
            order.append(f"{tag}:exit")

    await asyncio.gather(worker("a", 0.02), worker("b", 0.02))
    # Because concurrency=1, b can't enter until a exits.
    assert order == ["a:enter", "a:exit", "b:enter", "b:exit"]


async def test_distinct_hosts_do_not_contend() -> None:
    reg = SlotRegistry(default=1)
    # Same backend, different hosts -> different semaphores.
    events: list[str] = []

    async def worker(host: str, tag: str) -> None:
        async with reg.semaphore_for(_cfg(host)):
            events.append(f"{tag}:enter")
            await asyncio.sleep(0.01)
            events.append(f"{tag}:exit")

    await asyncio.gather(worker("h1", "a"), worker("h2", "b"))
    assert set(events) == {"a:enter", "a:exit", "b:enter", "b:exit"}
    # Both should have entered before either exited.
    assert events.index("a:enter") < events.index("b:exit")
    assert events.index("b:enter") < events.index("a:exit")


async def test_set_limit_after_first_use_raises() -> None:
    reg = SlotRegistry()
    reg.semaphore_for(_cfg("127.0.0.1:2"))
    with pytest.raises(RuntimeError, match="already in use"):
        reg.set_limit(backend="llamacpp", host="127.0.0.1:2", concurrency=2)


async def test_acquire_uses_global_registry() -> None:
    registry.reset()
    registry.set_limit(backend="llamacpp", host="127.0.0.1:3", concurrency=1)
    order: list[str] = []

    async def worker(tag: str) -> None:
        async with acquire(_cfg("127.0.0.1:3")):
            order.append(f"{tag}:enter")
            await asyncio.sleep(0.01)
            order.append(f"{tag}:exit")

    await asyncio.gather(worker("a"), worker("b"))
    assert order == ["a:enter", "a:exit", "b:enter", "b:exit"]
    registry.reset()

# --- from test_slots_rate_limit.py ---
pytestmark = pytest.mark.asyncio


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _cfg(host: str = "h1", *, max_tokens: int = 100) -> Configuration:
    return Configuration(
        backend="llamacpp", host=host, model="m",
        sampling=Sampling(max_tokens=max_tokens),
    )


@pytest.fixture(autouse=True)
def _reset_global_registry() -> None:
    registry.reset()
    yield
    registry.reset()


# ---------- SlidingCounter unit ----------

async def test_sliding_counter_blocks_and_unblocks_on_window_rollover() -> None:
    clock = FakeClock()
    c = SlidingCounter(limit=2, time_fn=clock)
    c.charge(1)
    c.charge(1)
    assert c.current() == 2

    t = asyncio.create_task(c.acquire(1))
    await asyncio.sleep(0)
    assert not t.done()

    clock.advance(61.0)
    # Waking is driven by the next operation that observes the expired window.
    c.set_limit(2)  # no-op limit change; triggers _wake → _expire
    await asyncio.wait_for(t, timeout=0.1)


async def test_sliding_counter_zero_is_unlimited() -> None:
    c = SlidingCounter(limit=0)
    await c.acquire(10_000)  # should not block
    c.charge(10_000)
    assert c.current() == 0  # unlimited → no bookkeeping


async def test_sliding_counter_negative_raises() -> None:
    with pytest.raises(ValueError):
        SlidingCounter(limit=-1)
    c = SlidingCounter(limit=5)
    with pytest.raises(ValueError):
        c.set_limit(-2)


# ---------- Registry & acquire ----------

async def test_rpm_blocks_second_request_until_window_clears() -> None:
    clock = FakeClock()
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", rpm=1)
    # Swap in deterministic clock on the RPM counter.
    reg._rpm[("llamacpp", "h1")] = SlidingCounter(limit=1, time_fn=clock)

    cfg = _cfg("h1")
    rpm = reg._rpm[("llamacpp", "h1")]

    # Use the counter directly (acquire() itself uses the global registry).
    await rpm.acquire(1)
    rpm.charge(1)

    t = asyncio.create_task(rpm.acquire(1))
    await asyncio.sleep(0)
    assert not t.done()

    clock.advance(61.0)
    rpm.set_limit(1)  # triggers wake after expiry
    await asyncio.wait_for(t, timeout=0.1)
    _ = cfg  # silence unused


async def test_tpm_charges_on_settle_and_reconciles_reserve() -> None:
    clock = FakeClock()
    registry.set_limit(backend="llamacpp", host="h1", tpm=1000)
    tpm = registry._tpm[("llamacpp", "h1")]
    tpm._time_fn = clock  # deterministic

    cfg = _cfg("h1", max_tokens=100)  # reserve = 2 * 100 = 200
    async with acquire(cfg) as slot:
        assert tpm.current() == 200  # provisional
        slot.settle(tokens=900)
    assert tpm.current() == 900  # reserve refunded, actual charged


async def test_rpm_and_tpm_stack() -> None:
    clock = FakeClock()
    registry.set_limit(backend="llamacpp", host="h1", rpm=10, tpm=500)
    rpm = registry._rpm[("llamacpp", "h1")]
    tpm = registry._tpm[("llamacpp", "h1")]
    rpm._time_fn = clock
    tpm._time_fn = clock

    cfg = _cfg("h1", max_tokens=100)  # reserve = 200 per call

    # First call fine.
    async with acquire(cfg) as slot:
        slot.settle(tokens=400)
    # TPM now at 400. A second call's reserve (200) would push to 600 > 500.

    # Second acquire should block on TPM.
    t = asyncio.create_task(_run_and_settle(cfg, tokens=0))
    await asyncio.sleep(0.05)
    assert not t.done()

    clock.advance(61.0)
    tpm.set_limit(500)  # kick the wake path
    await asyncio.wait_for(t, timeout=0.2)


async def _run_and_settle(cfg: Configuration, *, tokens: int) -> None:
    async with acquire(cfg) as slot:
        slot.settle(tokens=tokens)


async def test_concurrency_unchanged_without_rpm_tpm() -> None:
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", concurrency=1)
    order: list[str] = []

    async def worker(tag: str) -> None:
        async with reg.semaphore_for(_cfg("h1")):
            order.append(f"{tag}:enter")
            await asyncio.sleep(0.01)
            order.append(f"{tag}:exit")

    await asyncio.gather(worker("a"), worker("b"))
    assert order == ["a:enter", "a:exit", "b:enter", "b:exit"]


async def test_default_zero_overhead_no_gates() -> None:
    cfg = _cfg("h1")
    start = time.monotonic()
    for _ in range(1000):
        async with acquire(cfg) as slot:
            slot.settle(tokens=0)
    elapsed = time.monotonic() - start
    assert elapsed < 0.5  # generous: per-iter overhead must be trivial


async def test_settle_is_idempotent() -> None:
    registry.set_limit(backend="llamacpp", host="h1", tpm=1000)
    tpm = registry._tpm[("llamacpp", "h1")]
    cfg = _cfg("h1", max_tokens=100)
    async with acquire(cfg) as slot:
        slot.settle(tokens=100)
        slot.settle(tokens=100)  # second call ignored
    assert tpm.current() == 100


async def test_reset_clears_all_counters() -> None:
    registry.set_limit(
        backend="llamacpp", host="h1", concurrency=1, rpm=5, tpm=500
    )
    assert registry._rpm_limits
    assert registry._tpm_limits
    assert registry._concurrency
    registry.reset()
    assert not registry._rpm
    assert not registry._tpm
    assert not registry._rpm_limits
    assert not registry._tpm_limits
    assert not registry._concurrency
    assert not registry._semaphores


async def test_unknown_endpoint_uses_default_concurrency() -> None:
    cfg = _cfg("never-configured")
    # No limits set; acquire must succeed and yield a no-op token.
    async with acquire(cfg) as slot:
        slot.settle(tokens=0)
    # No RPM / TPM counters were created.
    assert registry.rpm_for(cfg) is None
    assert registry.tpm_for(cfg) is None


async def test_set_limit_partial_update_preserves_other_fields() -> None:
    registry.set_limit(backend="llamacpp", host="h1", rpm=100)
    assert registry._rpm_limits[("llamacpp", "h1")] == 100
    registry.set_limit(backend="llamacpp", host="h1", tpm=5000)
    assert registry._rpm_limits[("llamacpp", "h1")] == 100
    assert registry._tpm_limits[("llamacpp", "h1")] == 5000


async def test_rpm_zero_means_unlimited() -> None:
    registry.set_limit(backend="llamacpp", host="h1", rpm=0, tpm=0)
    cfg = _cfg("h1")
    for _ in range(50):
        async with acquire(cfg) as slot:
            slot.settle(tokens=1_000_000)  # would blow any finite tpm


async def test_negative_limits_raise() -> None:
    with pytest.raises(ValueError):
        registry.set_limit(backend="llamacpp", host="h1", rpm=-1)
    with pytest.raises(ValueError):
        registry.set_limit(backend="llamacpp", host="h1", tpm=-1)
    with pytest.raises(ValueError):
        registry.set_limit(backend="llamacpp", host="h1", concurrency=0)


async def test_concurrency_cannot_change_after_first_acquire() -> None:
    registry.set_limit(backend="llamacpp", host="h1", concurrency=2)
    cfg = _cfg("h1")
    async with acquire(cfg) as slot:
        slot.settle(tokens=0)
    with pytest.raises(RuntimeError, match="already in use"):
        registry.set_limit(backend="llamacpp", host="h1", concurrency=3)


async def test_rpm_can_be_updated_mid_flight() -> None:
    registry.set_limit(backend="llamacpp", host="h1", rpm=5)
    registry.set_limit(backend="llamacpp", host="h1", rpm=50)
    rpm = registry._rpm[("llamacpp", "h1")]
    assert rpm.limit == 50


async def test_settle_on_error_releases_reserve() -> None:
    registry.set_limit(backend="llamacpp", host="h1", tpm=1000)
    tpm = registry._tpm[("llamacpp", "h1")]
    cfg = _cfg("h1", max_tokens=100)
    with pytest.raises(RuntimeError):
        async with acquire(cfg):
            assert tpm.current() == 200
            raise RuntimeError("boom")
    # Reserve released via context-manager finally.
    assert tpm.current() == 0
