"""Dotted-path resolution over an Agent subtree.

A "path" names a node by the chain of attribute names under which each
child was attached. The root is named by the empty string (or the
literal ``"self"``); otherwise each segment must be a key in the
current node's ``_children``. Walking composites by ``_children`` —
rather than by payload inspection — keeps this consistent with the
"composites are pure routers" invariant.
"""

from __future__ import annotations

from typing import Any

from ..core.agent import Agent


def resolve(agent: Agent[Any, Any], path: str) -> Agent[Any, Any]:
    """Walk ``_children`` by attribute name and return the named node.

    ``path=""`` or ``"self"`` returns ``agent`` unchanged. Any segment
    missing from the current node's ``_children`` raises ``KeyError``
    with the full path and the offending segment.
    """
    if path == "" or path == "self":
        return agent

    current: Agent[Any, Any] = agent
    for segment in path.split("."):
        children = current._children
        if segment not in children:
            raise KeyError(
                f"no child named {segment!r} at path {path!r}; "
                f"available: {sorted(children)}"
            )
        current = children[segment]
    return current
