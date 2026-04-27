"""Task: short-form summarization.

50 synthesized (doc, one-sentence summary) pairs.
Primary metric: Rouge on the `summary` field.
"""

from __future__ import annotations

from typing import Any

from operad import Agent
from operad.benchmark import BenchmarkTask
from operad.metrics import Rouge
from operad.optim.losses import MetricLoss

from ._config import default_config
from ._data import (
    DocIn,
    SummaryOut,
    make_summarization_dataset,
)
from ._offline import OFFLINE_CFG, OfflineSummaryLeaf

DATASET = make_summarization_dataset(n=50, seed=42)

METRICS = [Rouge(field="summary")]

LOSS_FN = MetricLoss(METRICS[0])


# ---------------------------------------------------------------------------
# Seed agent: minimal prompt
# ---------------------------------------------------------------------------

class _Summarizer(Agent[DocIn, SummaryOut]):
    input = DocIn
    output = SummaryOut
    role = "You are a summarization assistant."
    task = "Summarize the given text in one sentence."
    rules: list[str] = []


class _SummarizerHandEdit(Agent[DocIn, SummaryOut]):
    input = DocIn
    output = SummaryOut
    role = "You are a concise summarization assistant who distills the core idea of any text."
    task = (
        "Write a single informative sentence that captures the most important fact "
        "or conclusion from the source text. Aim for 12–20 words."
    )
    rules = [
        "Output exactly one sentence ending with a period.",
        "Do not start with 'The text says' or similar meta-phrases.",
        "Preserve key proper nouns and technical terms from the source.",
    ]


def make_seed_agent(offline: bool = False) -> Agent[DocIn, SummaryOut]:
    if offline:
        return OfflineSummaryLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _Summarizer(config=default_config())


def make_hand_edit_agent(offline: bool = False) -> Agent[DocIn, SummaryOut]:
    if offline:
        return OfflineSummaryLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _SummarizerHandEdit(config=default_config())


def make_sweep_grid() -> dict[str, list[Any]]:
    return {
        "config.sampling.temperature": [0.0, 0.4, 0.8],
        "task": [
            _Summarizer.task,
            _SummarizerHandEdit.task,
            (
                "Condense the source text into a single clear sentence that conveys "
                "the main point. Keep it under 25 words."
            ),
        ],
    }


TASK = BenchmarkTask(
    key="sum",
    name="summarization",
    dataset=DATASET,
    metrics=METRICS,
    make_seed_agent=make_seed_agent,
    make_hand_edit_agent=make_hand_edit_agent,
    make_sweep_grid=make_sweep_grid,
    loss=LOSS_FN,
)
