"""Serialisable snapshot of an `Agent`'s declared state.

`AgentState` captures the mutable, user-facing parts of an agent — persona,
task, rules, few-shot examples, configuration, and the nested structure of
its children — without any build-time or runtime plumbing (strands state,
computation graph). It is the weight-equivalent surface for evolutionary
search, A/B prompt comparison, and hyperparameter sweeps.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .config import Configuration


class AgentState(BaseModel):
    """Pydantic snapshot of an Agent's state, round-trippable via `load_state`.

    `examples` are stored as dumped dicts because typed round-trip across
    processes would require the caller's `In`/`Out` classes; the target
    agent already knows its contract at `load_state` time and reconstructs
    typed `Example` instances from the dicts.

    `class_name`, `input_type_name`, and `output_type_name` are diagnostic —
    they are not enforced on load; the caller owns loading into a
    structurally-compatible agent.
    """

    class_name: str
    role: str
    task: str
    rules: list[str]
    examples: list[dict[str, Any]]
    config: Configuration | None = None
    input_type_name: str
    output_type_name: str
    children: dict[str, "AgentState"] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)


AgentState.model_rebuild()
