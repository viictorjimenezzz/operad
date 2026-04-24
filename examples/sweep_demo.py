"""Sweep: run a 2x2 parameter grid in parallel.

Runs offline — no model server required.

Uses a hand-rolled leaf that echoes its own `task` length. Shows the
shape of a `SweepReport` and the ``(parameters, output)`` layout of
each cell.

Run:
    uv run python examples/sweep_demo.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio

from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.core.config import Sampling
from operad.algorithms import Sweep


class Question(BaseModel):
    text: str = Field(description="A question to answer.")


class Answer(BaseModel):
    length: int = Field(default=0, description="Length of the active task string.")


class _EchoLeaf(Agent[Question, Answer]):
    input = Question
    output = Answer

    async def forward(self, x: Question) -> Answer:  # type: ignore[override]
        return Answer.model_construct(length=len(self.task))


async def main(offline: bool = False) -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="offline",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )
    seed = _EchoLeaf(config=cfg, task="seed")
    await seed.abuild()

    sweep = Sweep(
        {
            "task": ["be terse.", "think step by step, then answer."],
            "role": ["critic", "guide"],
        },
    )
    sweep.seed = seed
    report = await sweep.run(Question(text="capital of France?"))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
