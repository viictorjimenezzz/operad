"""Task: tool-call selection.

50 instructions across 5 tools.
Primary metric: ExactMatch on tool_name.
Secondary metric: Contains on tool_args (expected key present).
"""

from __future__ import annotations

from typing import Any

from operad import Agent
from operad.metrics import Contains, ExactMatch
from operad.optim.loss import LossFromMetric

from ._config import default_config
from ._shared import (
    OFFLINE_CFG,
    OfflineToolLeaf,
    ToolIn,
    ToolOut,
    _TOOLS,
    make_tool_use_dataset,
)

DATASET = make_tool_use_dataset(n=50, seed=42)

METRICS = [ExactMatch(), Contains(field="tool_args")]

LOSS_FN = LossFromMetric(METRICS[0])


# ---------------------------------------------------------------------------
# Seed agent: minimal prompt
# ---------------------------------------------------------------------------

_TOOL_LIST = ", ".join(_TOOLS)


class _ToolSelector(Agent[ToolIn, ToolOut]):
    input = ToolIn
    output = ToolOut
    role = "You are a tool-routing assistant."
    task = (
        f"Given a user instruction, select the most appropriate tool and provide "
        f"the required arguments as a JSON string. Available tools: {_TOOL_LIST}."
    )
    rules: list[str] = []


class _ToolSelectorHandEdit(Agent[ToolIn, ToolOut]):
    input = ToolIn
    output = ToolOut
    role = "You are a precise tool-routing assistant that maps instructions to API calls."
    task = (
        f"Analyze the user instruction and output the correct tool_name and tool_args. "
        f"tool_name must be one of: {_TOOL_LIST}. "
        f"tool_args must be a valid JSON string with the key arguments for that tool."
    )
    rules = [
        "tool_name must be the exact string from the allowed list — no variations.",
        "tool_args must be valid JSON with at least one key relevant to the instruction.",
        "For weather queries always include a 'city' key; for calculations include 'expression'.",
    ]


def make_seed_agent(offline: bool = False) -> Agent[ToolIn, ToolOut]:
    if offline:
        return OfflineToolLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _ToolSelector(config=default_config())


def make_hand_edit_agent(offline: bool = False) -> Agent[ToolIn, ToolOut]:
    if offline:
        return OfflineToolLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _ToolSelectorHandEdit(config=default_config())


def make_sweep_grid() -> dict[str, list[Any]]:
    return {
        "config.sampling.temperature": [0.0, 0.2, 0.5],
        "task": [
            _ToolSelector.task,
            _ToolSelectorHandEdit.task,
            (
                f"Map the user instruction to a tool call. Choose tool_name from: "
                f"{_TOOL_LIST}. Return tool_args as compact JSON."
            ),
        ],
    }
