"""Offline tests for ``SandboxedTool``: subprocess layer is mocked."""

from __future__ import annotations
import asyncio
import platform
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from operad.runtime.launchers import SandboxedTool
import json
from unittest.mock import AsyncMock, patch
from operad.runtime.launchers import PooledSandboxedTool, SandboxPool


# --- from test_sandbox.py ---
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

# --- from test_sandbox_pool.py ---
pytestmark = pytest.mark.asyncio


class _AddTool_test_sandbox_pool:
    name = "add"

    async def call(self, args: dict[str, Any]) -> Any:
        return args["a"] + args["b"]


class _Stream:
    def __init__(self) -> None:
        self._q: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._eof = False

    async def readline(self) -> bytes:
        if self._eof and self._q.empty():
            return b""
        item = await self._q.get()
        if item is None:
            self._eof = True
            return b""
        return item

    def push(self, line: bytes) -> None:
        self._q.put_nowait(line)

    def close(self) -> None:
        self._q.put_nowait(None)


class _FakeStdin:
    def __init__(self, on_write) -> None:
        self._on_write = on_write
        self._closed = False

    def write(self, data: bytes) -> None:
        if not self._closed:
            self._on_write(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True

    def is_closing(self) -> bool:
        return self._closed


class FakeProc:
    """A controllable fake of ``asyncio.subprocess.Process`` that echoes
    JSON-lines requests back as successful responses."""

    def __init__(self, *, stall: bool = False, error: bool = False) -> None:
        self.stall = stall
        self.error = error
        self.stdout = _Stream()
        self.stderr = _Stream()
        self.returncode: int | None = None
        self._exit = asyncio.Event()
        self.requests: list[dict] = []

        def _on_write(data: bytes) -> None:
            line = data.decode().strip()
            if not line:
                return
            req = json.loads(line)
            self.requests.append(req)
            if self.stall:
                return
            if self.error:
                resp = {"id": req["id"], "ok": False, "error": "boom"}
            else:
                resp = {
                    "id": req["id"],
                    "ok": True,
                    "result": {"echoed": req["args"]},
                }
            self.stdout.push((json.dumps(resp) + "\n").encode())

        self.stdin = _FakeStdin(_on_write)

    def kill(self) -> None:
        if self.returncode is None:
            self.returncode = -9
        self._exit.set()
        self.stdout.close()
        self.stderr.close()

    async def wait(self) -> int:
        await self._exit.wait()
        return self.returncode or 0


def _spawner(procs: list[FakeProc]):
    it = iter(procs)

    def _spawn(*args: Any, **kwargs: Any) -> FakeProc:
        return next(it)

    return _spawn


async def test_spawn_count_matches_size() -> None:
    procs = [FakeProc() for _ in range(2)]
    spawn = AsyncMock(side_effect=_spawner(procs))
    with patch(
        "operad.runtime.launchers.pool.asyncio.create_subprocess_exec",
        new=spawn,
    ):
        pool = SandboxPool(size=2, memory_mb=None)
        await pool.start()
        assert spawn.await_count == 2
        await pool.close()


async def test_concurrency_capped_by_size() -> None:
    procs = [FakeProc() for _ in range(2)]
    spawn = AsyncMock(side_effect=_spawner(procs))
    with patch(
        "operad.runtime.launchers.pool.asyncio.create_subprocess_exec",
        new=spawn,
    ):
        async with SandboxPool(size=2, memory_mb=None) as pool:
            results = await asyncio.gather(
                *[pool.call("mod:Add", {"i": i}) for i in range(10)]
            )
    assert spawn.await_count == 2
    assert len(results) == 10
    assert all(r == {"echoed": {"i": i}} for i, r in enumerate(results))


async def test_close_terminates_and_blocks_further_calls() -> None:
    procs = [FakeProc() for _ in range(2)]
    spawn = AsyncMock(side_effect=_spawner(procs))
    with patch(
        "operad.runtime.launchers.pool.asyncio.create_subprocess_exec",
        new=spawn,
    ):
        pool = SandboxPool(size=2, memory_mb=None)
        await pool.start()
        await pool.close()
        for p in procs:
            assert p.stdin.is_closing()
        with pytest.raises(RuntimeError) as exc:
            await pool.call("mod:Add", {})
    assert "closed" in str(exc.value)


async def test_timeout_isolates_worker() -> None:
    stalled = FakeProc(stall=True)
    healthy = FakeProc()
    spawn = AsyncMock(side_effect=_spawner([stalled, healthy]))
    with patch(
        "operad.runtime.launchers.pool.asyncio.create_subprocess_exec",
        new=spawn,
    ):
        async with SandboxPool(
            size=2, timeout_seconds=0.1, memory_mb=None
        ) as pool:
            call_a = asyncio.create_task(pool.call("mod:A", {"n": 1}))
            call_b = asyncio.create_task(pool.call("mod:A", {"n": 2}))
            results = await asyncio.gather(
                call_a, call_b, return_exceptions=True
            )
    errors = [r for r in results if isinstance(r, Exception)]
    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(errors) == 1
    assert "timed out" in str(errors[0])
    assert len(successes) == 1
    assert successes[0] == {"echoed": {"n": 2}} or successes[0] == {
        "echoed": {"n": 1}
    }
    assert stalled.returncode is not None


async def test_windows_raises_from_test_sandbox_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError) as exc:
        SandboxPool(size=2, memory_mb=None)
    assert "POSIX" in str(exc.value)


async def test_pooled_tool_delegates_with_qualified_name() -> None:
    procs = [FakeProc()]
    spawn = AsyncMock(side_effect=_spawner(procs))
    with patch(
        "operad.runtime.launchers.pool.asyncio.create_subprocess_exec",
        new=spawn,
    ):
        async with SandboxPool(size=1, memory_mb=None) as pool:
            tool = PooledSandboxedTool(_AddTool_test_sandbox_pool(), pool=pool)
            assert tool.name == "add"
            assert asyncio.iscoroutinefunction(tool.call)
            result = await tool.call({"a": 2, "b": 3})
    assert result == {"echoed": {"a": 2, "b": 3}}
    assert procs[0].requests[0]["tool"].endswith(":_AddTool_test_sandbox_pool")
