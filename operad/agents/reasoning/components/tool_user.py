"""ToolUser leaf: dispatch typed tool calls against a fixed registry.

Override-forward leaf — looks up the named tool in the ``tools`` dict
passed at construction, validates ``x.args`` against the tool's declared
``args_schema``, invokes it, and wraps the return in ``ToolResult``.
Tool *selection* (deciding which tool to call) is out of scope for v1;
that's a composed pattern built on top.

No plugin discovery — a plain dict is the whole registry. Pass more at
construction time if you need more tools.

Canonical shape::

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

    user = ToolUser(tools={"add": AddTool()})
    await user.build().invoke(
        ToolCall[AddArgs](tool_name="add", args=AddArgs(a=1, b=2))
    )
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from ....core.agent import Agent
from ..schemas import ToolCall, ToolResult


Args = TypeVar("Args", bound=BaseModel)
Result = TypeVar("Result", bound=BaseModel)


class Tool(Protocol, Generic[Args, Result]):
    """A typed tool interface: named, with declared schemas and an async ``call``."""

    name: str
    args_schema: type[Args]
    result_schema: type[Result]

    async def call(self, args: Args) -> Result: ...


class ToolUser(Agent[ToolCall[Any], ToolResult[Any]]):
    input = ToolCall
    output = ToolResult

    role = "You dispatch typed tool calls."
    task = "Invoke the named tool with the given arguments and return the result."
    rules = (
        "If the tool is unknown, return ok=False with a descriptive error.",
        "If the tool raises, return ok=False with the exception message.",
    )
    default_sampling = {"temperature": 0.0}

    def __init__(
        self,
        *,
        tools: dict[str, Tool[Any, Any]],
        input: type[BaseModel] = ToolCall,
        output: type[BaseModel] = ToolResult,
    ) -> None:
        super().__init__(config=None, input=input, output=output)
        self._tools: dict[str, Tool[Any, Any]] = dict(tools)

    async def forward(self, x: ToolCall[Any]) -> ToolResult[Any]:  # type: ignore[override]
        tool = self._tools.get(x.tool_name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool {x.tool_name!r}")
        try:
            raw_args = x.args if isinstance(x.args, dict) else x.args.model_dump()
            typed_args = tool.args_schema.model_validate(raw_args)
            raw = await tool.call(typed_args)
            typed_result = (
                raw if isinstance(raw, BaseModel)
                else tool.result_schema.model_validate(raw)
            )
            return ToolResult(ok=True, result=typed_result)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


__all__ = ["Tool", "ToolCall", "ToolResult", "ToolUser"]
