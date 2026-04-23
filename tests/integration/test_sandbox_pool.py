"""Real-subprocess tests for ``SandboxPool``.

Opt-in: only runs when ``OPERAD_INTEGRATION=sandbox``.

    OPERAD_INTEGRATION=sandbox uv run pytest tests/integration/test_sandbox_pool.py -v
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import pytest

from operad.runtime.launchers import PooledSandboxedTool, SandboxPool


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "sandbox",
        reason="set OPERAD_INTEGRATION=sandbox to enable",
    ),
]


class AddTool:
    name = "add"

    async def call(self, args: dict[str, Any]) -> Any:
        return args["a"] + args["b"]


async def test_pool_amortises_cold_start() -> None:
    async with SandboxPool(size=2, timeout_seconds=10.0, memory_mb=None) as pool:
        tool = PooledSandboxedTool(AddTool(), pool=pool)
        started = time.perf_counter()
        results = await asyncio.gather(
            *[tool.call({"a": i, "b": 1}) for i in range(100)]
        )
        elapsed = time.perf_counter() - started
    assert results == [i + 1 for i in range(100)]
    # A single-shot launcher would cost ~100 * 100ms = 10s of cold
    # start. With a size=2 pool amortising that across two long-lived
    # workers, 100 calls should complete well inside 3s.
    assert elapsed < 3.0, f"100 pooled calls took {elapsed:.2f}s"


async def test_pool_reuses_workers_across_calls() -> None:
    async with SandboxPool(size=2, memory_mb=None) as pool:
        tool = PooledSandboxedTool(AddTool(), pool=pool)
        r1, r2 = await asyncio.gather(
            tool.call({"a": 1, "b": 2}),
            tool.call({"a": 10, "b": 20}),
        )
        r3 = await tool.call({"a": 7, "b": 7})
    assert (r1, r2, r3) == (3, 30, 14)
