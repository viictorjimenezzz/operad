"""Three-stage Pipeline: extract -> plan -> evaluate.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Shows typed edges across three different leaf kinds. ``build()``
verifies each handoff before any tokens are generated.

Run:
    uv run python examples/pipeline.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from operad import Pipeline
from operad.core.config import Sampling
from operad.agents import Evaluator, Extractor, Planner

from _config import local_config, server_reachable

_SCRIPT = "pipeline.py"


class Request(BaseModel):
    text: str = Field(description="A free-form user request.")


class Task(BaseModel):
    goal: str = Field(default="", description="The underlying goal distilled from the request.")
    constraints: list[str] = Field(default_factory=list, description="Any constraints the user mentioned.")


class Plan(BaseModel):
    steps: list[str] = Field(default_factory=list, description="Ordered, concrete steps.")


class Answer(BaseModel):
    reasoning: str = Field(default="", description="Brief reasoning over the plan.")
    answer: str = Field(default="", description="The final, user-facing answer.")


async def main(offline: bool = False) -> None:
    cfg = local_config(sampling=Sampling(temperature=0.2, max_tokens=2048))
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
    pipeline = Pipeline(
        Extractor(config=cfg, input=Request, output=Task),
        Planner(config=cfg, input=Task, output=Plan),
        Evaluator(config=cfg, input=Plan, output=Answer),
        input=Request,
        output=Answer,
    )
    await pipeline.abuild()
    result = await pipeline(Request(text="I want to learn Rust in a month on a budget."))
    print(result.response.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
