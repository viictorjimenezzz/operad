"""Curriculum callback."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Literal

from ..report import EpochReport
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer


class Curriculum(Callback):
    """Re-order each epoch's data by per-sample gradient severity."""

    _OVERRIDE_SAMPLER_TYPES = ("WeightedRandomSampler", "StratifiedSampler")

    def __init__(
        self,
        monitor: str = "severity_per_sample",
        mode: Literal["hard_first", "easy_first", "anneal"] = "hard_first",
        warmup_epochs: int = 1,
    ) -> None:
        if mode not in ("hard_first", "easy_first", "anneal"):
            raise ValueError(
                f"mode must be 'hard_first', 'easy_first', or 'anneal', got {mode!r}"
            )
        if warmup_epochs < 0:
            raise ValueError("warmup_epochs must be non-negative")
        self.monitor = monitor
        self.mode = mode
        self.warmup_epochs = warmup_epochs
        self._epoch_count: int = 0

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        self._epoch_count = 0
        sampler = getattr(getattr(trainer, "loader", None), "_sampler", None)
        if sampler is not None and type(sampler).__name__ in self._OVERRIDE_SAMPLER_TYPES:
            warnings.warn(
                f"Curriculum: loader uses {type(sampler).__name__}, whose natural "
                "ordering will be overridden by Curriculum.set_order().",
                UserWarning,
                stacklevel=2,
            )

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        self._epoch_count += 1

        loader = getattr(trainer, "loader", None)
        sampler = getattr(loader, "_sampler", None)
        if sampler is None or not hasattr(sampler, "set_order"):
            warnings.warn(
                "Curriculum: loader.sampler does not support set_order(); "
                "wrap it in PermutableSampler (operad.data.PermutableSampler).",
                UserWarning,
                stacklevel=2,
            )
            return

        severity_map: dict[int, float] = trainer.last_epoch_per_sample_severity
        if not severity_map:
            return

        indices = list(severity_map.keys())

        if self.mode == "hard_first":
            ordered = sorted(indices, key=lambda i: severity_map[i], reverse=True)
        elif self.mode == "easy_first":
            ordered = sorted(indices, key=lambda i: severity_map[i])
        else:
            if self._epoch_count <= self.warmup_epochs:
                ordered = sorted(indices, key=lambda i: severity_map[i], reverse=True)
            else:
                import random as _random

                ordered = indices[:]
                _random.shuffle(ordered)

        sampler.set_order(ordered)


__all__ = ["Curriculum"]
