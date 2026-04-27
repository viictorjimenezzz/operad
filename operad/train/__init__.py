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
    Curriculum,
    EarlyStopping,
    GradClip,
    HumanFeedbackCallback,
    LRLogger,
    MemoryRotation,
    PromptDrift,
    TracebackOnFailure,
)
from .progress import TrainerProgressObserver
from .report import EpochReport, TrainingReport
from .trainer import Trainer


__all__ = [
    "BestCheckpoint",
    "Callback",
    "Curriculum",
    "EarlyStopping",
    "EpochReport",
    "GradClip",
    "HumanFeedbackCallback",
    "LRLogger",
    "MemoryRotation",
    "PromptDrift",
    "TracebackOnFailure",
    "Trainer",
    "TrainerProgressObserver",
    "TrainingReport",
]
