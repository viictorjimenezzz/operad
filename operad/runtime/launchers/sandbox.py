"""Subprocess sandbox wrapper for the ``Tool`` protocol.

``SandboxedTool(inner)`` satisfies the same structural ``Tool`` contract
as its argument, so it drops into any ``ToolUser`` registry. Each
``call`` spawns a fresh Python interpreter running
``operad.runtime.launchers.sandbox_worker``, pipes the JSON args over
stdin, and reads the JSON result from stdout.

Constraints (v1):

- POSIX only (``resource.setrlimit`` is unavailable on Windows).
- The wrapped tool class must be importable by ``module:ClassName`` and
  constructible with no arguments.
- Args and results must be JSON-serialisable.
- Failures (non-zero exit, timeout) raise ``RuntimeError``. Callers
  typically run through ``ToolUser``, which already converts raised
  exceptions into ``ToolResult(ok=False, error=...)``.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
from asyncio.subprocess import PIPE
from typing import Any


class SandboxedTool:
    def __init__(
        self,
        tool: Any,
        *,
        timeout_seconds: float = 10.0,
        memory_mb: int | None = 256,
    ) -> None:
        if platform.system() == "Windows":
            raise RuntimeError(
                "SandboxedTool requires POSIX; "
                "resource.setrlimit is unavailable on Windows."
            )
        self.name: str = tool.name
        self._module: str = tool.__class__.__module__
        self._qualname: str = tool.__class__.__name__
        self._timeout: float = timeout_seconds
        self._mem_bytes: int | None = (
            memory_mb * 1024 * 1024 if memory_mb else None
        )

    def _apply_limits(self) -> None:
        # preexec_fn runs in the forked child before exec. RLIMIT_AS caps
        # virtual address space; macOS honours it loosely (≠ RSS), good
        # enough for v1.
        import resource

        if self._mem_bytes is not None:
            resource.setrlimit(
                resource.RLIMIT_AS, (self._mem_bytes, self._mem_bytes)
            )

    async def call(self, args: dict[str, Any]) -> Any:
        cmd = [
            sys.executable,
            "-m",
            "operad.runtime.launchers.sandbox_worker",
            f"--tool={self._module}:{self._qualname}",
        ]
        # Inherit the parent's sys.path via PYTHONPATH so the worker can
        # import the wrapped tool's module.
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            env=env,
            preexec_fn=self._apply_limits if self._mem_bytes else None,
        )
        payload = json.dumps(args).encode()
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"SandboxedTool {self.name!r} timed out after "
                f"{self._timeout}s"
            )
        if proc.returncode != 0:
            raise RuntimeError(
                f"sandbox worker exit {proc.returncode}: "
                f"{stderr.decode(errors='replace')[:500]}"
            )
        return json.loads(stdout.decode())["result"]


__all__ = ["SandboxedTool"]
