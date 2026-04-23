"""Sweep: run a 2x2 parameter grid in parallel, offline.

Uses a hand-rolled leaf that echoes its own `task` length so the demo
runs with no network. Shows the shape of a `SweepReport` and the
``(parameters, output)`` layout of each cell.

    uv run python examples/sweep_demo.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad import Agent, Configuration, Sweep


class Question(BaseModel):
    text: str = Field(description="A question to answer.")


class Answer(BaseModel):
    length: int = Field(default=0, description="Length of the active task string.")


class _EchoLeaf(Agent[Question, Answer]):
    input = Question
    output = Answer

    async def forward(self, x: Question) -> Answer:  # type: ignore[override]
        return Answer.model_construct(length=len(self.task))


async def _main() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="offline",
        temperature=0.0,
        max_tokens=16,
    )
    seed = _EchoLeaf(config=cfg, task="seed")
    await seed.abuild()

    sweep = Sweep(
        seed,
        {
            "task": ["be terse.", "think step by step, then answer."],
            "role": ["critic", "guide"],
        },
    )
    report = await sweep.run(Question(text="capital of France?"))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
