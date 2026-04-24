"""Tests for ``ToolUser``: typed-registry dispatch, error envelopes."""

from __future__ import annotations
import pytest
from pydantic import BaseModel
from operad.agents import ToolCall, ToolResult, ToolUser
from operad.utils.hashing import hash_schema


# --- from test_tool_user.py ---
pytestmark = pytest.mark.asyncio


class _AddArgs(BaseModel):
    a: int
    b: int


class _AddResult(BaseModel):
    sum: int


class _AddTool:
    name = "add"
    args_schema = _AddArgs
    result_schema = _AddResult

    async def call(self, args: _AddArgs) -> _AddResult:
        return _AddResult(sum=args.a + args.b)


class _Empty(BaseModel):
    pass


class _RaisingTool:
    name = "boom"
    args_schema = _Empty
    result_schema = _Empty

    async def call(self, args: _Empty) -> _Empty:
        raise RuntimeError("kaboom")


async def test_tool_user_builds_without_config() -> None:
    u = ToolUser(tools={"add": _AddTool()})
    assert u.config is None
    await u.abuild()


async def test_known_tool_returns_ok_true_with_result() -> None:
    u = await ToolUser(tools={"add": _AddTool()}).abuild()
    out = await u(ToolCall[_AddArgs](tool_name="add", args=_AddArgs(a=2, b=3)))
    assert isinstance(out.response, ToolResult)
    assert out.response.ok is True
    assert isinstance(out.response.result, _AddResult)
    assert out.response.result.sum == 5
    assert out.response.error == ""


async def test_unknown_tool_returns_ok_false_with_error() -> None:
    u = await ToolUser(tools={"add": _AddTool()}).abuild()
    out = await u(ToolCall[_AddArgs](tool_name="missing", args=_AddArgs(a=0, b=0)))
    assert out.response.ok is False
    assert out.response.result is None
    assert "missing" in out.response.error


async def test_raising_tool_returns_ok_false_with_message() -> None:
    u = await ToolUser(tools={"boom": _RaisingTool()}).abuild()
    out = await u(ToolCall[_Empty](tool_name="boom", args=_Empty()))
    assert out.response.ok is False
    assert out.response.result is None
    assert "kaboom" in out.response.error

# --- from test_typed_tool.py ---
pytestmark = pytest.mark.asyncio


class AddArgs(BaseModel):
    a: int
    b: int


class AddResult(BaseModel):
    sum: int


class AddTool:
    name = "add"
    args_schema = AddArgs
    result_schema = AddResult

    async def call(self, args: AddArgs) -> AddResult:
        return AddResult(sum=args.a + args.b)


class SearchArgs(BaseModel):
    query: str
    k: int = 5


class SearchResult(BaseModel):
    hits: list[str] = []


class SearchTool:
    name = "search"
    args_schema = SearchArgs
    result_schema = SearchResult

    async def call(self, args: SearchArgs) -> SearchResult:
        return SearchResult(hits=[args.query] * args.k)


class RaisingTool:
    name = "boom"
    args_schema = AddArgs
    result_schema = AddResult

    async def call(self, args: AddArgs) -> AddResult:
        raise RuntimeError("kaboom")


async def test_typed_args_round_trip() -> None:
    u = await ToolUser(tools={"add": AddTool()}).abuild()
    call = ToolCall[AddArgs](tool_name="add", args=AddArgs(a=2, b=3))
    out = await u(call)
    assert isinstance(out.response, ToolResult)
    assert out.response.ok is True
    assert isinstance(out.response.result, AddResult)
    assert out.response.result.sum == 5


async def test_distinct_args_schemas_produce_distinct_hashes() -> None:
    # Cassette keys depend on hash_schema distinguishing tools by their
    # declared args_schema. If a future refactor makes these collide, the
    # cassette layer silently caches wrong results across tools.
    assert hash_schema(AddTool.args_schema) != hash_schema(SearchTool.args_schema)
    assert hash_schema(ToolCall[AddArgs]) != hash_schema(ToolCall[SearchArgs])


async def test_unknown_tool_path() -> None:
    u = await ToolUser(tools={"add": AddTool()}).abuild()
    out = await u(ToolCall[AddArgs](tool_name="missing", args=AddArgs(a=1, b=2)))
    assert out.response.ok is False
    assert out.response.result is None
    assert "missing" in out.response.error


async def test_validation_error_path() -> None:
    u = await ToolUser(tools={"boom": RaisingTool()}).abuild()
    out = await u(ToolCall[AddArgs](tool_name="boom", args=AddArgs(a=1, b=2)))
    assert out.response.ok is False
    assert out.response.result is None
    assert "kaboom" in out.response.error


async def test_tool_user_builds_at_any_parametrisation() -> None:
    u = ToolUser(tools={"add": AddTool(), "search": SearchTool()})
    built = await u.abuild()
    assert built is u
