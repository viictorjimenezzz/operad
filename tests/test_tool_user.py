"""Tests for ``ToolUser``: dict-registry dispatch, error envelopes."""

from __future__ import annotations

from typing import Any

import pytest

from operad import ToolCall, ToolResult, ToolUser


pytestmark = pytest.mark.asyncio


class _AddTool:
    name = "add"

    async def call(self, args: dict[str, Any]) -> Any:
        return args["a"] + args["b"]


class _RaisingTool:
    name = "boom"

    async def call(self, args: dict[str, Any]) -> Any:
        raise RuntimeError("kaboom")


async def test_tool_user_builds_without_config() -> None:
    u = ToolUser(tools={"add": _AddTool()})
    assert u.config is None
    await u.abuild()


async def test_known_tool_returns_ok_true_with_result() -> None:
    u = await ToolUser(tools={"add": _AddTool()}).abuild()
    out = await u(ToolCall(tool_name="add", args={"a": 2, "b": 3}))
    assert isinstance(out.response, ToolResult)
    assert out.response.ok is True
    assert out.response.result == 5
    assert out.response.error == ""


async def test_unknown_tool_returns_ok_false_with_error() -> None:
    u = await ToolUser(tools={"add": _AddTool()}).abuild()
    out = await u(ToolCall(tool_name="missing", args={}))
    assert out.response.ok is False
    assert "missing" in out.response.error


async def test_raising_tool_returns_ok_false_with_message() -> None:
    u = await ToolUser(tools={"boom": _RaisingTool()}).abuild()
    out = await u(ToolCall(tool_name="boom", args={}))
    assert out.response.ok is False
    assert "kaboom" in out.response.error
