"""Best-checkpoint callback."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ...benchmark.evaluate import EvalReport
from ...core.freeze import freeze_agent
from .callback import Callback
from .early_stopping import _better, _extract_metric

if TYPE_CHECKING:
    from ..trainer import Trainer


class BestCheckpoint(Callback):
    """Freeze the agent to disk whenever the monitored metric improves."""

    def __init__(
        self,
        path: str | Path,
        monitor: str = "val_loss",
        mode: Literal["min", "max"] = "min",
        save_optimizer: bool = False,
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        self.path = Path(path)
        self.monitor = monitor
        self.mode = mode
        self.save_optimizer = bool(save_optimizer)
        self._best: float = float("inf") if mode == "min" else float("-inf")

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        current = _extract_metric(report, self.monitor)
        if math.isnan(current):
            return
        if not _better(current, self._best, self.mode):
            return
        self._best = current
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.save_optimizer:
            freeze_agent(trainer.agent, self.path, optimizer=trainer.optimizer)
        else:
            freeze_agent(trainer.agent, self.path)


__all__ = ["BestCheckpoint"]
