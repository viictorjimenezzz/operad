"""Tests for the typed ``Tool[Args, Result]`` boundary.

Covers the guarantees that stream 2-4 introduces:

- ``ToolCall[Args]`` / ``ToolResult[Result]`` round-trip structured types.
- Tools with distinct ``args_schema`` hash distinctly under
  ``hash_schema`` — the load-bearing property for cassette keying.
- Unknown-tool and raising-tool paths surface as ``ok=False`` with a
  populated ``error``.
- ``ToolUser`` builds at ``Agent[ToolCall[Any], ToolResult[Any]]``.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad.agents import ToolCall, ToolResult, ToolUser
from operad.utils.hashing import hash_schema


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
