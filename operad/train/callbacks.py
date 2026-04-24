"""`Callback` base class and the standard concrete callbacks.

`Callback` is a concrete class with seven async no-op lifecycle hooks;
users subclass and override the ones they care about. Concrete
implementations here cover the canonical PyTorch-Lightning surface:
early stopping, best checkpointing, textual-gradient clipping, drift
warnings, LR logging, and a tape-size guardrail.

Callbacks are invoked by `Trainer` in insertion order. A callback that
wants to halt training sets ``trainer._should_stop = True``; `Trainer`
checks the flag at the end of every epoch.
"""

from __future__ import annotations

import logging
import math
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..benchmark.evaluate import EvalReport
from ..core.freeze import freeze_agent
from ..data.loader import Batch
from .report import EpochReport, TrainingReport

if TYPE_CHECKING:
    from .trainer import Trainer


_LOGGER = logging.getLogger("operad.train")


class Callback:
    """Base class for every `Trainer` callback.

    Every hook is an async no-op; subclasses override only what they need.
    """

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


def _better(a: float, b: float, mode: Literal["min", "max"]) -> bool:
    """True when ``a`` improves over ``b`` under ``mode``."""
    if math.isnan(a):
        return False
    if math.isnan(b):
        return True
    return a < b if mode == "min" else a > b


def _extract_metric(report: EvalReport, monitor: str) -> float:
    """Pull ``monitor`` off ``report.summary`` with NaN fallback."""
    return float(report.summary.get(monitor, float("nan")))


class EarlyStopping(Callback):
    """Stop training when the monitored metric stops improving.

    Tracks the best value seen on `on_validation_end`. When the metric
    fails to improve by at least ``min_delta`` for ``patience``
    consecutive validations, the callback sets
    ``trainer._should_stop = True``.
    """

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
        if self._stale > self.patience:
            trainer._should_stop = True


class BestCheckpoint(Callback):
    """Freeze the agent to disk whenever the monitored metric improves."""

    def __init__(
        self,
        path: str | Path,
        monitor: str = "val_loss",
        mode: Literal["min", "max"] = "min",
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        self.path = Path(path)
        self.monitor = monitor
        self.mode = mode
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
        freeze_agent(trainer.agent, self.path)


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


class PromptDrift(Callback):
    """Warn when ``agent.hash_content`` changes too many times in a fit."""

    def __init__(self, max_hash_changes: int = 5) -> None:
        if max_hash_changes < 0:
            raise ValueError("max_hash_changes must be non-negative")
        self.max_hash_changes = max_hash_changes
        self._last_hash: str | None = None
        self._changes: int = 0
        self._warned: bool = False

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        self._last_hash = trainer.agent.hash_content
        self._changes = 0
        self._warned = False

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        h = report.hash_content
        if self._last_hash is not None and h != self._last_hash:
            self._changes += 1
        self._last_hash = h
        if self._changes > self.max_hash_changes and not self._warned:
            warnings.warn(
                f"agent hash_content changed {self._changes} times, "
                f"exceeding threshold {self.max_hash_changes}",
                RuntimeWarning,
                stacklevel=2,
            )
            self._warned = True


class LearningRateLogger(Callback):
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


EarlyStoppingSpec = EarlyStopping


__all__ = [
    "BestCheckpoint",
    "Callback",
    "EarlyStopping",
    "EarlyStoppingSpec",
    "GradClip",
    "LearningRateLogger",
    "MemoryRotation",
    "PromptDrift",
]
