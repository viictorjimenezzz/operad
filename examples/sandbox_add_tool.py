"""Sibling module for ``sandbox_tooluser.py``.

Hosts ``AddTool`` outside of ``__main__`` so the sandbox subprocess can
import it by ``sandbox_add_tool:AddTool``.

``AddTool.call`` accepts either a typed ``AddArgs`` (the normal
``ToolUser`` path) or a dict (the sandbox worker path, which ships JSON
over stdin). The sandbox worker also requires the return value to be
JSON-serialisable, so we return a dict that ``ToolUser.forward`` then
validates back into ``AddResult``.
"""

from __future__ import annotations

from pydantic import BaseModel


class AddArgs(BaseModel):
    a: int
    b: int


class AddResult(BaseModel):
    sum: int


class AddTool:
    name = "add"
    args_schema = AddArgs
    result_schema = AddResult

    async def call(self, args: AddArgs | dict) -> dict:
        typed = args if isinstance(args, AddArgs) else AddArgs.model_validate(args)
        return AddResult(sum=typed.a + typed.b).model_dump()
