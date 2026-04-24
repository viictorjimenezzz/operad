"""operad: a typed, composable agent library built on top of strands."""

from __future__ import annotations

from .core import (
    Agent,
    AgentDiff,
    AgentGraph,
    AgentState,
    Backend,
    Change,
    Configuration,
    Example,
    OperadOutput,
    abuild_agent,
    build_agent,
)
from .agents import Parallel, Pipeline
from .datasets import Dataset
from .eval import evaluate
from .metrics import Metric
from .runtime.trace import Trace
from .utils.errors import BuildError, BuildReason
from . import tracing

__all__ = [
    "Agent",
    "AgentDiff",
    "AgentGraph",
    "AgentState",
    "Backend",
    "BuildError",
    "BuildReason",
    "Change",
    "Configuration",
    "Dataset",
    "Example",
    "Metric",
    "OperadOutput",
    "Parallel",
    "Pipeline",
    "Trace",
    "abuild_agent",
    "build_agent",
    "evaluate",
    "tracing",
]
