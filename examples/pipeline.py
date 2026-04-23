"""Three-stage Pipeline: extract -> plan -> evaluate.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Shows typed edges across three different leaf kinds. ``build()``
verifies each handoff before any tokens are generated.

    uv run python examples/pipeline.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad import Evaluator, Extractor, Pipeline, Planner

from _config import local_config


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


async def _main() -> None:
    cfg = local_config(temperature=0.2, max_tokens=512)
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
    asyncio.run(_main())
