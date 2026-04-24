"""Beam: generate 3 candidate answers, let a Critic pick the winner.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

``Beam`` is an *algorithm* (plain class with ``run(x)``), not an Agent.
It orchestrates a generator Agent and a judge Agent with metric
feedback. Its ``run(x)`` returns the ``top_k`` highest-scored
candidates.

Run:
    uv run python examples/beam.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from operad.core.config import Sampling
from operad.agents import Critic, Reasoner
from operad.algorithms import Beam

from _config import local_config, server_reachable

_SCRIPT = "beam.py"


class Question(BaseModel):
    text: str = Field(description="A trivia question.")


class Answer(BaseModel):
    reasoning: str = Field(default="", description="Short justification.")
    answer: str = Field(default="", description="A concise factual answer.")


async def main(offline: bool = False) -> None:
    cfg = local_config(sampling=Sampling(temperature=0.4, max_tokens=2048))
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if offline:
        print(f"[{_SCRIPT}] --offline not supported for this example (needs a real model); exiting 0 as no-op.")
        return
    if not server_reachable(cfg.host):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} — start llama-server or pass --offline",
            file=sys.stderr,
        )
        raise SystemExit(1)
    beam = Beam(n=2)
    beam.generator = Reasoner(config=cfg, input=Question, output=Answer)
    beam.judge = Critic(config=cfg)
    await beam.generator.abuild()
    await beam.judge.abuild()

    winners = await beam.run(Question(text="What is the tallest mountain on Earth?"))
    for w in winners:
        print(w.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
