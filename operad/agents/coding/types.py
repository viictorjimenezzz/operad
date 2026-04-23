"""Deprecated alias for :mod:`operad.agents.coding.schemas`.

Importing from this module emits a :class:`DeprecationWarning` and
re-exports the canonical schemas. Remove in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "operad.agents.coding.types is renamed to operad.agents.coding.schemas; "
    "the old name will be removed in a future release",
    DeprecationWarning,
    stacklevel=2,
)

from .schemas import (  # noqa: E402,F401
    DiffChunk,
    PRDiff,
    PRSummary,
    ReviewComment,
    ReviewReport,
)

__all__ = [
    "DiffChunk",
    "PRDiff",
    "PRSummary",
    "ReviewComment",
    "ReviewReport",
]
