"""`operad.train` — fit / evaluate / predict entry point.

The library's PyTorch-Lightning analog. `Trainer` composes a built
`Agent`, an `Optimizer`, a `Loss`, an optional LR scheduler, metrics,
and callbacks into a single `fit()` call that returns a
`TrainingReport`.
"""

from __future__ import annotations

from .callbacks import (
    BestCheckpoint,
    Callback,
    EarlyStopping,
    EarlyStoppingSpec,
    GradClip,
    LearningRateLogger,
    MemoryRotation,
    PromptDrift,
)
from .report import EpochReport, TrainingReport
from .trainer import Trainer


__all__ = [
    "BestCheckpoint",
    "Callback",
    "EarlyStopping",
    "EarlyStoppingSpec",
    "EpochReport",
    "GradClip",
    "LearningRateLogger",
    "MemoryRotation",
    "PromptDrift",
    "Trainer",
    "TrainingReport",
]
