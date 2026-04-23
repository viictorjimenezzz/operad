"""Deprecated alias for :mod:`operad.agents.memory.schemas`.

Importing from this module emits a :class:`DeprecationWarning` and
re-exports the canonical schemas. Remove in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "operad.agents.memory.shapes is renamed to operad.agents.memory.schemas; "
    "the old name will be removed in a future release",
    DeprecationWarning,
    stacklevel=2,
)

from .schemas import (  # noqa: E402,F401
    Belief,
    Beliefs,
    Conversation,
    Summary,
    Turn,
    UserModel,
)

__all__ = [
    "Belief",
    "Beliefs",
    "Conversation",
    "Summary",
    "Turn",
    "UserModel",
]
