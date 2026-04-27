"""Optimizer implementations."""

from __future__ import annotations

from operad.optim.optimizers.ape import (
    APEInput,
    APEOptimizer,
    APEOutput,
    CandidateGenerator,
)
from operad.optim.optimizers.evo import EvoGradient
from operad.optim.optimizers.momentum import (
    GradSummarizer,
    MomentumInput,
    MomentumTextGrad,
)
from operad.optim.optimizers.opro import (
    OPROAgent,
    OPROHistoryEntry,
    OPROInput,
    OPROOptimizer,
    OPROOutput,
)
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.optimizers.tgd import RewriterFactory, TextualGradientDescent

__all__ = [
    "APEInput",
    "APEOptimizer",
    "APEOutput",
    "CandidateGenerator",
    "EvoGradient",
    "GradSummarizer",
    "MomentumInput",
    "MomentumTextGrad",
    "OPROAgent",
    "OPROHistoryEntry",
    "OPROInput",
    "OPROOptimizer",
    "OPROOutput",
    "Optimizer",
    "ParamGroup",
    "RewriterFactory",
    "TextualGradientDescent",
]
