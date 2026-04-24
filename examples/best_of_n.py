"""Best-of-N: generate 3 candidate answers, let a Critic pick the winner.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

``BestOfN`` is an *algorithm* (plain class with ``run(x)``), not an
Agent. It orchestrates a generator Agent and a judge Agent with metric
feedback. Its ``run(x)`` returns the highest-scored candidate.

    uv run python examples/best_of_n.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad.core.config import Sampling
from operad.agents import Critic, Reasoner
from operad.algorithms import BestOfN

from _config import local_config


class Question(BaseModel):
    text: str = Field(description="A trivia question.")


class Answer(BaseModel):
    reasoning: str = Field(default="", description="Short justification.")
    answer: str = Field(default="", description="A concise factual answer.")


async def _main() -> None:
    cfg = local_config(sampling=Sampling(temperature=0.9, max_tokens=256))
    generator = Reasoner(config=cfg, input=Question, output=Answer)
    judge = Critic(config=cfg)

    await generator.abuild()
    await judge.abuild()

    bon = BestOfN(generator=generator, judge=judge, n=3)
    winner = await bon.run(Question(text="What is the tallest mountain on Earth?"))
    print(winner.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
