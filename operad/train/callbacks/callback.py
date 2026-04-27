"""Base class for trainer callbacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...benchmark.evaluate import EvalReport
from ...data.loader import Batch
from ..report import EpochReport, TrainingReport

if TYPE_CHECKING:
    from ..trainer import Trainer


class Callback:
    """Base class for every `Trainer` callback."""

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        return None

    async def on_epoch_start(
        self, trainer: "Trainer[Any, Any]", epoch: int
    ) -> None:
        return None

    async def on_batch_start(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
    ) -> None:
        return None

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        return None

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        return None

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        return None

    async def on_fit_end(
        self, trainer: "Trainer[Any, Any]", report: TrainingReport
    ) -> None:
        return None


__all__ = ["Callback"]
