"""Early stopping callback."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Literal

from ...benchmark.evaluate import EvalReport
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer


def _better(a: float, b: float, mode: Literal["min", "max"]) -> bool:
    if math.isnan(a):
        return False
    if math.isnan(b):
        return True
    return a < b if mode == "min" else a > b


def _extract_metric(report: EvalReport, monitor: str) -> float:
    return float(report.summary.get(monitor, float("nan")))


class EarlyStopping(Callback):
    """Stop training when the monitored metric stops improving."""

    def __init__(
        self,
        monitor: str = "val_loss",
        mode: Literal["min", "max"] = "min",
        patience: int = 3,
        min_delta: float = 1e-4,
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        if patience < 0:
            raise ValueError("patience must be non-negative")
        if min_delta < 0:
            raise ValueError("min_delta must be non-negative")
        self.monitor = monitor
        self.mode = mode
        self.patience = patience
        self.min_delta = min_delta
        self._best: float = float("inf") if mode == "min" else float("-inf")
        self._stale: int = 0

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        current = _extract_metric(report, self.monitor)
        if math.isnan(current):
            return
        delta = (
            self._best - current if self.mode == "min" else current - self._best
        )
        if delta > self.min_delta:
            self._best = current
            self._stale = 0
            return
        self._stale += 1
        if self._stale >= self.patience:
            trainer._should_stop = True


__all__ = ["EarlyStopping"]
