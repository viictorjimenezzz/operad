"""operad: a typed, composable agent library built on top of strands."""

from __future__ import annotations

from .agents import (
    Action,
    Actor,
    Answer,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Observation,
    Parallel,
    Pipeline,
    Planner,
    ReAct,
    Reasoner,
    Task,
    Thought,
)
from .algorithms import BestOfN, Candidate, Score
from .core import (
    Agent,
    AgentGraph,
    Backend,
    Configuration,
    Edge,
    Example,
    Node,
    abuild_agent,
    build_agent,
    to_json,
    to_mermaid,
)
from .metrics import ExactMatch, JsonValid, Latency, Metric
from .models import resolve_model
from .runtime import SlotRegistry, set_limit
from .utils.errors import BuildError, BuildReason

__all__ = [
    "Action",
    "Actor",
    "Agent",
    "AgentGraph",
    "Answer",
    "Backend",
    "BestOfN",
    "BuildError",
    "BuildReason",
    "Candidate",
    "Classifier",
    "Configuration",
    "Critic",
    "Edge",
    "Evaluator",
    "ExactMatch",
    "Example",
    "Extractor",
    "JsonValid",
    "Latency",
    "Metric",
    "Node",
    "Observation",
    "Parallel",
    "Pipeline",
    "Planner",
    "ReAct",
    "Reasoner",
    "Score",
    "SlotRegistry",
    "Task",
    "Thought",
    "abuild_agent",
    "build_agent",
    "resolve_model",
    "set_limit",
    "to_json",
    "to_mermaid",
]
