"""Dotted-path helpers over an Agent tree.

Two flavours coexist:

- ``resolve_parent`` / ``set_path`` walk plain Python attribute access,
  used by ``Sweep`` to address nested fields like
  ``"reasoner.config.temperature"``.
- ``_resolve`` walks an Agent's ``_children`` dict by attribute name,
  used by the mutation ops in ``operad.utils.ops``. An empty path
  returns the root; a missing child raises ``BuildError``.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .errors import BuildError

if TYPE_CHECKING:
    from ..core.agent import Agent


def resolve_parent(root: Any, path: str) -> tuple[Any, str]:
    """Walk `path` on `root` and return ``(parent, final_segment)``.

    ``resolve_parent(agent, "reasoner.config.temperature")`` returns
    ``(agent.reasoner.config, "temperature")``. Raises ``KeyError`` if
    any intermediate segment is missing, naming the segment and the
    prefix that failed.
    """
    if not path:
        raise KeyError("empty path")
    segments = path.split(".")
    obj = root
    for i, seg in enumerate(segments[:-1]):
        if not hasattr(obj, seg):
            prefix = ".".join(segments[: i + 1])
            raise KeyError(
                f"path segment {seg!r} not found (while resolving {prefix!r})"
            )
        obj = getattr(obj, seg)
    return obj, segments[-1]


def set_path(root: Any, path: str, value: Any) -> None:
    """Assign `value` at `path` on `root` via attribute access."""
    parent, attr = resolve_parent(root, path)
    setattr(parent, attr, value)


def _resolve(agent: "Agent[Any, Any]", path: str) -> "Agent[Any, Any]":
    """Return the descendant of `agent` at the given dotted path.

    ``""`` returns `agent` itself. Segments are looked up in ``_children``
    by attribute name; a missing segment raises ``BuildError``.
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
