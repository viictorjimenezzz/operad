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

__all__ = ["BuildError", "BuildReason"]
