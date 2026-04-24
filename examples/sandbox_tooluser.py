"""Wrap a trivial in-process ``Tool`` in ``SandboxedTool`` and call it.

The wrapped class must be importable by ``module:ClassName`` in the
worker subprocess. When a script is launched directly, its module is
``__main__`` — which the subprocess cannot re-import — so we put the
tool in a sibling module and add this directory to ``sys.path``.

Run:
    uv run python examples/sandbox_tooluser.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from sandbox_add_tool import AddTool  # noqa: E402

from operad.runtime.launchers import SandboxedTool  # noqa: E402


async def main(offline: bool = False) -> None:
    sandbox = SandboxedTool(AddTool(), timeout_seconds=5.0, memory_mb=None)
    result = await sandbox.call({"a": 2, "b": 3})
    print(f"sandboxed add(2, 3) = {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
