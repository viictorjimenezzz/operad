"""Offline evaluation demo: score a canned agent over a tiny dataset.

Runs offline — no model server required.

Runs five rows through a `FakeLeaf`-style agent and prints the resulting
`EvalReport` with per-row scores and per-metric means.

    uv run python examples/eval_loop.py
"""

from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, Field

from operad import Agent, Configuration, evaluate
from operad.eval import EvalReport
from operad.metrics import Contains, ExactMatch, Rouge1


class Question(BaseModel):
    text: str = Field(default="", description="The question to answer.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer text.")


class CannedAgent(Agent[Question, Answer]):
    """Deterministic agent that looks up answers in a dict."""

    input = Question
    output = Answer

    def __init__(self, *, config: Configuration, table: dict[str, str]) -> None:
        super().__init__(config=config)
        self.table = table

    async def forward(self, x: Question) -> Answer:
        return Answer(text=self.table.get(x.text, ""))


async def _main() -> None:
    cfg = Configuration(
        backend="llamacpp", host="127.0.0.1:0", model="offline", temperature=0.0,
    )
    agent = CannedAgent(
        config=cfg,
        table={
            "capital of france": "Paris is the capital of France.",
            "author of hamlet": "William Shakespeare wrote Hamlet.",
            "speed of light": "299792458 metres per second.",
            "largest planet": "Jupiter is the largest planet.",
            "sqrt of 144": "The square root of 144 is 12.",
        },
    )
    await agent.abuild()

    dataset = [
        (Question(text="capital of france"), Answer(text="Paris")),
        (Question(text="author of hamlet"), Answer(text="Shakespeare")),
        (Question(text="speed of light"), Answer(text="299792458")),
        (Question(text="largest planet"), Answer(text="Jupiter")),
        (Question(text="sqrt of 144"), Answer(text="12")),
    ]

    report: EvalReport = await evaluate(
        agent,
        dataset,
        [ExactMatch(), Contains(field="text"), Rouge1(field="text")],
    )
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
