"""ToolUser leaf: dispatch typed tool calls against a fixed registry.

Override-forward leaf — looks up the named tool in the ``tools`` dict
passed at construction, invokes it, and wraps the return value in a
``ToolResult``. Tool *selection* (deciding which tool to call) is out of
scope for v1; that's a composed pattern built on top.

No plugin discovery — a plain dict is the whole registry. Pass more at
construction time if you need more tools.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from ....core.agent import Agent, Example
from ..schemas import ToolCall, ToolResult


class Tool(Protocol):
    """A minimal tool interface: named, with an async ``call``."""

    name: str

    async def call(self, args: dict[str, Any]) -> Any: ...


class ToolUser(Agent[ToolCall, ToolResult]):
    input = ToolCall
    output = ToolResult

    role = "You dispatch typed tool calls."
    task = "Invoke the named tool with the given arguments and return the result."
    rules = (
        "If the tool is unknown, return ok=False with a descriptive error.",
        "If the tool raises, return ok=False with the exception message.",
    )
    examples = (
        Example[ToolCall, ToolResult](
            input=ToolCall(tool_name="add", args={"a": 1, "b": 2}),
            output=ToolResult(ok=True, result=3),
        ),
    )

    def __init__(
        self,
        *,
        tools: dict[str, Tool],
        input: type[BaseModel] = ToolCall,
        output: type[BaseModel] = ToolResult,
    ) -> None:
        super().__init__(config=None, input=input, output=output)
        self._tools = dict(tools)

    async def forward(self, x: ToolCall) -> ToolResult:  # type: ignore[override]
        tool = self._tools.get(x.tool_name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool {x.tool_name!r}")
        try:
            return ToolResult(ok=True, result=await tool.call(x.args))
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


__all__ = ["Tool", "ToolCall", "ToolResult", "ToolUser"]
