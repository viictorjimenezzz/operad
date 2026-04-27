"""Logging and traceback callbacks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...data.loader import Batch
from ...optim.backprop.traceback import PromptTraceback
from ..report import EpochReport
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer

_LOGGER = logging.getLogger("operad.train")


class LRLogger(Callback):
    """Log each epoch's per-group LRs at INFO."""

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        _LOGGER.info("epoch=%d lr=%s", report.epoch, report.lr)


class MemoryRotation(Callback):
    """Warn when a batch's tape(s) recorded more than ``max_tape_entries``."""

    def __init__(self, max_tape_entries: int = 10_000) -> None:
        if max_tape_entries < 1:
            raise ValueError("max_tape_entries must be >= 1")
        self.max_tape_entries = max_tape_entries

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        total = trainer._last_batch_tape_entries
        if total > self.max_tape_entries:
            _LOGGER.warning(
                "batch %d tape size %d exceeds threshold %d",
                step,
                total,
                self.max_tape_entries,
            )


class TracebackOnFailure(Callback):
    """Construct and log a `PromptTraceback` when ``loss > loss_threshold``."""

    def __init__(
        self,
        loss_threshold: float,
        *,
        save_dir: Path | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._loss_threshold = loss_threshold
        self._save_dir: Path | None = Path(save_dir) if save_dir is not None else None
        self._logger = logger or logging.getLogger("operad.train")

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        if loss <= self._loss_threshold:
            return

        tape = getattr(trainer, "_last_tape", None)
        last_grad = getattr(trainer, "_last_loss_grad", None)
        if tape is None or last_grad is None:
            self._logger.debug(
                "TracebackOnFailure: trainer does not expose `_last_tape` / "
                "`_last_loss_grad`; skipping (step=%d, loss=%.3f)",
                step,
                loss,
            )
            return

        tb = PromptTraceback.from_run(tape, last_grad)
        self._logger.warning(
            "Prompt traceback at step %d (loss=%.3f):\n%s", step, loss, tb
        )
        if self._save_dir is not None:
            self._save_dir.mkdir(parents=True, exist_ok=True)
            tb.save(self._save_dir / f"step-{step:05d}.ndjson")


__all__ = ["LRLogger", "MemoryRotation", "TracebackOnFailure"]
