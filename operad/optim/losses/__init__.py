"""Loss classes for textual-gradient training."""

from __future__ import annotations

from operad.optim.losses.hfeedback import HumanFeedbackLoss
from operad.optim.losses.judge import LLMAAJ
from operad.optim.losses.loss import CompositeLoss, Loss
from operad.optim.losses.metric import MetricLoss
from operad.optim.losses.schema import SchemaLoss

__all__ = [
    "CompositeLoss",
    "HumanFeedbackLoss",
    "LLMAAJ",
    "Loss",
    "MetricLoss",
    "SchemaLoss",
]
