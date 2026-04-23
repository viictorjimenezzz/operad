"""Real-subprocess tests for ``SandboxedTool``.

Opt-in: only runs when ``OPERAD_INTEGRATION=sandbox``.

    OPERAD_INTEGRATION=sandbox uv run pytest tests/integration/test_sandbox.py -v
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from operad.runtime.launchers import SandboxedTool


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "sandbox",
        reason="set OPERAD_INTEGRATION=sandbox to enable",
    ),
]


class EchoTool:
    name = "echo"

    async def call(self, args: dict[str, Any]) -> Any:
        return {"said": args.get("msg", "")}


class SleepTool:
    name = "sleep"

    async def call(self, args: dict[str, Any]) -> Any:
        time.sleep(args.get("seconds", 5))
        return "woke"


async def test_real_roundtrip() -> None:
    sandbox = SandboxedTool(EchoTool(), timeout_seconds=10.0, memory_mb=None)
    result = await sandbox.call({"msg": "hi"})
    assert result == {"said": "hi"}


async def test_real_timeout_kills() -> None:
    sandbox = SandboxedTool(SleepTool(), timeout_seconds=0.5, memory_mb=None)
    with pytest.raises(RuntimeError) as exc:
        await sandbox.call({"seconds": 5})
    assert "timed out" in str(exc.value)
