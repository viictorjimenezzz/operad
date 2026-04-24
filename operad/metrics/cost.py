"""Backward-compat shim — the canonical cost module is
``operad.runtime.cost``.

``CostTracker`` and the transitional ``_CostEvent`` are re-exported
here so ``from operad.metrics import CostTracker`` (and the internal
``from operad.metrics.cost import _CostEvent`` in tests) keeps working.
"""

from __future__ import annotations

from ..runtime.cost import CostTracker, _CostEvent

__all__ = ["CostTracker", "_CostEvent"]
