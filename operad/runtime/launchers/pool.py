"""Reusable sandbox worker pool.

``SandboxPool`` holds ``size`` long-lived sandbox worker subprocesses
speaking a JSON-lines request/response protocol on stdin/stdout. Each
``call()`` checks out an idle worker, writes one request line, awaits
the matching response, and returns the worker to the pool.

``PooledSandboxedTool`` wraps a tool and dispatches through a shared
``SandboxPool``, satisfying the structural ``Tool`` contract that
``ToolUser`` consumes.

Constraints (v1):

- POSIX only (``resource.setrlimit`` is unavailable on Windows).
- The wrapped tool class must be importable by ``module:ClassName`` and
  constructible with no arguments.
- Args and results must be JSON-serialisable.
- ``memory_mb`` applies to the whole worker process, not per call.
- Crashed or timed-out workers are dropped from the pool; no auto-
  restart in v1.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
import uuid
from asyncio.subprocess import PIPE
from typing import Any


def _preexec_factory(mem_bytes: int | None):
    if mem_bytes is None:
        return None

    def _apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

    return _apply


class _Worker:
    def __init__(self, proc: Any) -> None:
        self.proc = proc
        self.pending: dict[str, asyncio.Future] = {}
        self.alive: bool = True
        self.reader_task: asyncio.Task | None = None
        self.stderr_task: asyncio.Task | None = None

    async def _reader(self) -> None:
        stdout = self.proc.stdout
        while True:
            line = await stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode())
            except Exception:
                continue
            fut = self.pending.pop(msg.get("id", ""), None)
            if fut is None or fut.done():
                continue
            if msg.get("ok"):
                fut.set_result(msg.get("result"))
            else:
                fut.set_exception(
                    RuntimeError(msg.get("error", "sandbox worker error"))
                )
        self.alive = False
        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("sandbox worker exited"))
        self.pending.clear()

    async def _stderr_drain(self) -> None:
        stderr = self.proc.stderr
        while True:
            chunk = await stderr.readline()
            if not chunk:
                break


class SandboxPool:
    def __init__(
        self,
        *,
        size: int = 4,
        timeout_seconds: float = 10.0,
        memory_mb: int | None = 256,
    ) -> None:
        if platform.system() == "Windows":
            raise RuntimeError(
                "SandboxPool requires POSIX; "
                "resource.setrlimit is unavailable on Windows."
            )
        if size < 1:
            raise ValueError("SandboxPool size must be >= 1")
        self._size = size
        self._timeout = timeout_seconds
        self._mem_bytes: int | None = (
            memory_mb * 1024 * 1024 if memory_mb else None
        )
        self._workers: list[_Worker] = []
        self._idle: asyncio.Queue[_Worker] = asyncio.Queue()
        self._closed: bool = False
        self._started: bool = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        cmd = [
            sys.executable,
            "-m",
            "operad.runtime.launchers.sandbox_worker",
            "--pool",
        ]
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
        preexec = _preexec_factory(self._mem_bytes)
        for _ in range(self._size):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                preexec_fn=preexec,
            )
            worker = _Worker(proc)
            worker.reader_task = asyncio.create_task(worker._reader())
            worker.stderr_task = asyncio.create_task(worker._stderr_drain())
            self._workers.append(worker)
            await self._idle.put(worker)

    async def call(self, tool_qualified: str, args: dict) -> Any:
        if self._closed:
            raise RuntimeError("SandboxPool is closed")
        if not self._started:
            await self.start()
        worker = await self._idle.get()
        if not worker.alive or self._closed:
            raise RuntimeError("SandboxPool is closed")
        req_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        worker.pending[req_id] = fut
        payload = (
            json.dumps({"id": req_id, "tool": tool_qualified, "args": args})
            + "\n"
        ).encode()
        try:
            worker.proc.stdin.write(payload)
            await worker.proc.stdin.drain()
            result = await asyncio.wait_for(fut, timeout=self._timeout)
        except asyncio.TimeoutError:
            await self._kill_worker(worker)
            raise RuntimeError(
                f"SandboxPool call timed out after {self._timeout}s"
            )
        except Exception:
            if worker.alive and not self._closed:
                await self._idle.put(worker)
            else:
                await self._kill_worker(worker)
            raise
        await self._idle.put(worker)
        return result

    async def _kill_worker(self, worker: _Worker) -> None:
        worker.alive = False
        try:
            worker.proc.kill()
        except ProcessLookupError:
            pass
        try:
            await worker.proc.wait()
        except Exception:
            pass
        for fut in list(worker.pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("sandbox worker killed"))
        worker.pending.clear()
        if worker in self._workers:
            self._workers.remove(worker)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for w in list(self._workers):
            try:
                if w.proc.stdin is not None:
                    w.proc.stdin.close()
            except Exception:
                pass
        for w in list(self._workers):
            try:
                await asyncio.wait_for(w.proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                try:
                    w.proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    await w.proc.wait()
                except Exception:
                    pass
            except Exception:
                pass
        for w in list(self._workers):
            for task in (w.reader_task, w.stderr_task):
                if task is None:
                    continue
                try:
                    await task
                except Exception:
                    pass
            for fut in list(w.pending.values()):
                if not fut.done():
                    fut.set_exception(RuntimeError("SandboxPool closed"))
            w.pending.clear()
        self._workers.clear()

    async def __aenter__(self) -> "SandboxPool":
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


class PooledSandboxedTool:
    def __init__(self, tool: Any, *, pool: SandboxPool) -> None:
        self._tool = tool
        self._pool = pool
        self.name: str = tool.name
        self._qualified: str = (
            f"{tool.__class__.__module__}:{tool.__class__.__name__}"
        )

    async def call(self, args: dict[str, Any]) -> Any:
        return await self._pool.call(self._qualified, args)


__all__ = ["SandboxPool", "PooledSandboxedTool"]
