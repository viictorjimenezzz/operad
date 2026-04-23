"""Old schema module paths must still work, emit DeprecationWarning,
and re-export identical types as the new canonical locations.
"""

from __future__ import annotations

import importlib

import pytest


def test_coding_types_deprecated_shim() -> None:
    import operad.agents.coding.types as old_mod
    import operad.agents.coding.schemas as new_mod

    # Force re-execution of the shim so the warning is observable.
    with pytest.warns(DeprecationWarning, match="coding.types"):
        importlib.reload(old_mod)

    for name in ("DiffChunk", "PRDiff", "PRSummary", "ReviewComment", "ReviewReport"):
        assert getattr(old_mod, name) is getattr(new_mod, name)


def test_memory_shapes_deprecated_shim() -> None:
    import operad.agents.memory.shapes as old_mod
    import operad.agents.memory.schemas as new_mod

    with pytest.warns(DeprecationWarning, match="memory.shapes"):
        importlib.reload(old_mod)

    for name in ("Belief", "Beliefs", "Conversation", "Summary", "Turn", "UserModel"):
        assert getattr(old_mod, name) is getattr(new_mod, name)
