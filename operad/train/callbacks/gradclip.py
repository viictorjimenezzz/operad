"""Textual-gradient clipping callback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...data.loader import Batch
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer


class GradClip(Callback):
    """Cap ``param.grad.severity`` in place before `optimizer.step()`."""

    def __init__(self, max_severity: float = 0.5) -> None:
        if max_severity <= 0:
            raise ValueError("max_severity must be positive")
        self.max_severity = max_severity

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        for group in trainer.optimizer.param_groups:
            for p in group.params:
                if p.grad is not None and p.grad.severity > self.max_severity:
                    p.grad = p.grad.model_copy(
                        update={"severity": self.max_severity}
                    )


__all__ = ["GradClip"]
