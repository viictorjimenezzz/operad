"""Tests for `SlotRegistry.occupancy()` — the public snapshot API."""

from __future__ import annotations

import asyncio

import pytest

from operad import Configuration
from operad.core.config import Sampling
from operad.runtime import SlotOccupancy, SlotRegistry, acquire, registry
from operad.runtime.slots import SlidingCounter

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
        backend="llamacpp",
        host=host,
        model="m",
        sampling=Sampling(max_tokens=max_tokens),
    )


@pytest.fixture(autouse=True)
def _reset_global_registry() -> None:
    registry.reset()
    yield
    registry.reset()


async def test_occupancy_empty_registry() -> None:
    reg = SlotRegistry()
    assert reg.occupancy() == []


async def test_occupancy_reports_registered_keys() -> None:
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", concurrency=2, rpm=10, tpm=100)
    reg.set_limit(backend="openai", host="h2", rpm=50)

    snap = reg.occupancy()
    assert len(snap) == 2
    by_key = {(o.backend, o.host): o for o in snap}
    assert ("llamacpp", "h1") in by_key
    assert ("openai", "h2") in by_key
    assert all(isinstance(o, SlotOccupancy) for o in snap)


async def test_occupancy_reflects_concurrency_used() -> None:
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", concurrency=2)
    cfg = _cfg("h1")
    sem = reg.semaphore_for(cfg)

    async with sem:
        inside = {(o.backend, o.host): o for o in reg.occupancy()}[("llamacpp", "h1")]
        assert inside.concurrency_used == 1
        assert inside.concurrency_cap == 2

    after = {(o.backend, o.host): o for o in reg.occupancy()}[("llamacpp", "h1")]
    assert after.concurrency_used == 0


async def test_occupancy_reflects_rpm_tpm_charges() -> None:
    clock = FakeClock()
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", rpm=10, tpm=500)
    reg._rpm[("llamacpp", "h1")] = SlidingCounter(limit=10, time_fn=clock)
    reg._tpm[("llamacpp", "h1")] = SlidingCounter(limit=500, time_fn=clock)

    reg._rpm[("llamacpp", "h1")].charge(3)
    reg._tpm[("llamacpp", "h1")].charge(120)

    o = reg.occupancy()[0]
    assert o.rpm_used == 3
    assert o.rpm_cap == 10
    assert o.tpm_used == 120
    assert o.tpm_cap == 500


async def test_occupancy_caps_pass_through_with_unlimited() -> None:
    reg = SlotRegistry()
    reg.set_limit(backend="llamacpp", host="h1", concurrency=3, rpm=100, tpm=0)
    # Force rpm/tpm counter creation; tpm=0 means unlimited.
    o = {(x.backend, x.host): x for x in reg.occupancy()}[("llamacpp", "h1")]
    assert o.concurrency_cap == 3
    assert o.rpm_cap == 100
    assert o.tpm_cap is None


async def test_occupancy_default_concurrency_cap_when_not_set() -> None:
    reg = SlotRegistry(default=7)
    reg.set_limit(backend="llamacpp", host="h1", rpm=5)
    o = reg.occupancy()[0]
    # No explicit concurrency → falls back to registry default.
    assert o.concurrency_cap == 7
    assert o.concurrency_used == 0


async def test_occupancy_snapshot_does_not_deadlock_while_slot_held() -> None:
    registry.set_limit(backend="llamacpp", host="h1", concurrency=1)
    cfg = _cfg("h1")

    gate = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with acquire(cfg) as slot:
            gate.set()
            await release.wait()
            slot.settle(tokens=0)

    task = asyncio.create_task(holder())
    await gate.wait()

    o = {(x.backend, x.host): x for x in registry.occupancy()}[("llamacpp", "h1")]
    assert o.concurrency_used == 1
    assert o.concurrency_cap == 1

    release.set()
    await task

    o2 = {(x.backend, x.host): x for x in registry.occupancy()}[("llamacpp", "h1")]
    assert o2.concurrency_used == 0
