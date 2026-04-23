"""Offline tests for ``SandboxedTool``: subprocess layer is mocked."""

from __future__ import annotations

import asyncio
import platform
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from operad.runtime.launchers import SandboxedTool


pytestmark = pytest.mark.asyncio


class _AddTool:
    name = "add"

    async def call(self, args: dict[str, Any]) -> Any:
        return args["a"] + args["b"]


def _proc_mock(
    *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0
) -> MagicMock:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


async def test_success_roundtrip() -> None:
    proc = _proc_mock(stdout=b'{"result": 5}', returncode=0)
    with patch(
        "operad.runtime.launchers.sandbox.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        sandbox = SandboxedTool(_AddTool(), memory_mb=None)
        result = await sandbox.call({"a": 2, "b": 3})
    assert result == 5


async def test_nonzero_exit_raises_with_stderr() -> None:
    proc = _proc_mock(stderr=b"traceback: boom", returncode=1)
    with patch(
        "operad.runtime.launchers.sandbox.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        sandbox = SandboxedTool(_AddTool(), memory_mb=None)
        with pytest.raises(RuntimeError) as exc:
            await sandbox.call({})
    assert "exit 1" in str(exc.value)
    assert "boom" in str(exc.value)


async def test_timeout_kills_process() -> None:
    proc = _proc_mock()

    async def _raise_timeout(coro: Any = None, *a: Any, **kw: Any) -> None:
        # `asyncio.wait_for(proc.communicate(...), timeout=...)` passes the
        # inner coroutine positionally. Close it so the AsyncMock it came
        # from doesn't raise `RuntimeWarning: coroutine was never awaited`.
        if hasattr(coro, "close"):
            coro.close()
        raise asyncio.TimeoutError

    with (
        patch(
            "operad.runtime.launchers.sandbox.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ),
        patch(
            "operad.runtime.launchers.sandbox.asyncio.wait_for",
            new=_raise_timeout,
        ),
    ):
        sandbox = SandboxedTool(_AddTool(), timeout_seconds=0.1, memory_mb=None)
        with pytest.raises(RuntimeError) as exc:
            await sandbox.call({})
    assert "timed out" in str(exc.value)
    proc.kill.assert_called_once()


async def test_name_forwarded() -> None:
    sandbox = SandboxedTool(_AddTool(), memory_mb=None)
    assert sandbox.name == "add"


async def test_windows_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError) as exc:
        SandboxedTool(_AddTool(), memory_mb=None)
    assert "POSIX" in str(exc.value)


async def test_satisfies_tool_protocol_shape() -> None:
    sandbox = SandboxedTool(_AddTool(), memory_mb=None)
    assert isinstance(sandbox.name, str)
    assert asyncio.iscoroutinefunction(sandbox.call)
