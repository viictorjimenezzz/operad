"""Dotted-path resolution over an agent's child tree.

`_resolve(agent, "a.b.c")` walks `_children` by attribute name. Empty
path returns the agent itself; a missing segment raises
`BuildError("prompt_incomplete", ...)`. Factored here so mutation ops,
sweeps, and introspection share one implementation.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .errors import BuildError

if TYPE_CHECKING:
    from ..core.agent import Agent


def _resolve(agent: "Agent[Any, Any]", path: str) -> "Agent[Any, Any]":
    """Return the descendant of `agent` at the given dotted path.

    `""` returns `agent` itself. Segments are looked up in `_children`
    by attribute name; a missing segment raises `BuildError`.
    """
    if path == "":
        return agent
    current: Any = agent
    for segment in path.split("."):
        children = getattr(current, "_children", None)
        if not children or segment not in children:
            raise BuildError(
                "prompt_incomplete",
                f"no child named {segment!r} at path {path!r}",
                agent=type(agent).__name__,
            )
        current = children[segment]
    return current
