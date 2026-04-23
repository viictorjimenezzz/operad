"""Launchers — strategies for running tool/agent payloads out of process.

v1 ships a single-shot subprocess sandbox (``SandboxedTool``) plus a
reusable worker pool (``SandboxPool`` + ``PooledSandboxedTool``) that
amortises interpreter cold-start across many tool calls.
"""

from __future__ import annotations

from .pool import PooledSandboxedTool, SandboxPool
from .sandbox import SandboxedTool


__all__ = ["SandboxedTool", "SandboxPool", "PooledSandboxedTool"]
