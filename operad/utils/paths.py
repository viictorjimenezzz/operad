"""Dotted-path attribute helpers.

Shared by algorithms that need to address nested fields on an Agent
tree — e.g. ``"reasoner.config.temperature"``. Kept deliberately small:
plain attribute access, no Pydantic-aware deep replacement. Composite
children, leaf instance attributes, and ``Configuration`` fields are all
regular Python attributes, so ``setattr`` is sufficient.
"""

from __future__ import annotations

from typing import Any


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
