"""Small cross-cutting helpers shared by the foundation and plugins.

Note: ``ops`` and ``paths`` are deliberately *not* re-exported here.
They depend on ``operad.core.agent``, which in turn imports from
``operad.utils.errors`` during its own module initialisation — eager
re-exports would deadlock that cycle. Import them directly::

    from operad.utils.ops import AppendRule, CompoundOp
    from operad.utils.paths import resolve
"""

from __future__ import annotations

from .errors import BuildError, BuildReason
from .ops import (
    AppendExample,
    AppendRule,
    CompoundOp,
    DropExample,
    DropRule,
    EditTask,
    Op,
    ReplaceRule,
    SetBackend,
    SetModel,
    SetTemperature,
    TweakRole,
)
from .paths import _resolve

__all__ = [
    "AppendExample",
    "AppendRule",
    "BuildError",
    "BuildReason",
    "CompoundOp",
    "DropExample",
    "DropRule",
    "EditTask",
    "Op",
    "ReplaceRule",
    "SetBackend",
    "SetModel",
    "SetTemperature",
    "TweakRole",
    "_resolve",
]
