"""Launchers — strategies for running tool/agent payloads out of process.

v1 ships a single subprocess-based sandbox (`SandboxedTool`). Future
launchers (pool-backed, macOS Terminal) will live alongside it.
"""

from __future__ import annotations

from .sandbox import SandboxedTool


__all__ = ["SandboxedTool"]
