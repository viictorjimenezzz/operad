"""Dispatch concurrent tool calls through a reusable ``SandboxPool``.

Two long-lived worker subprocesses amortise the ~100ms interpreter
cold-start that ``SandboxedTool`` pays on every call.

Run:
    uv run python examples/sandbox_pool_demo.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from sandbox_add_tool import AddTool  # noqa: E402

from operad.runtime.launchers import PooledSandboxedTool, SandboxPool  # noqa: E402


async def main(offline: bool = False) -> None:
    async with SandboxPool(size=2, timeout_seconds=5.0, memory_mb=None) as pool:
        tool = PooledSandboxedTool(AddTool(), pool=pool)
        started = time.perf_counter()
        results = await asyncio.gather(
            *[tool.call({"a": i, "b": i + 1}) for i in range(10)]
        )
        elapsed = time.perf_counter() - started
    print(f"10 pooled calls in {elapsed:.3f}s -> {results}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
