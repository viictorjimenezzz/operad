"""Sibling module for ``sandbox_tooluser.py``.

Hosts ``AddTool`` outside of ``__main__`` so the sandbox subprocess can
import it by ``sandbox_add_tool:AddTool``.
"""

from __future__ import annotations

from typing import Any


class AddTool:
    name = "add"

    async def call(self, args: dict[str, Any]) -> Any:
        return args["a"] + args["b"]
