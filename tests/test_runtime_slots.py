"""Tests for the concurrency-slot registry."""

from __future__ import annotations

import asyncio

import pytest

from operad import Configuration
from operad.runtime import SlotRegistry
from operad.runtime import acquire, registry


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
