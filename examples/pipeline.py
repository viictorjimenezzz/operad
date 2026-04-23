"""Three-stage Pipeline: extract -> plan -> evaluate.

Shows typed edges across three different leaf kinds. ``build()``
verifies each handoff before any tokens are generated.

Requires a local llama-server at ``$OPERAD_LLAMACPP_HOST`` (default
``127.0.0.1:8080``). Set ``OPERAD_LLAMACPP_MODEL`` to pick a model.

    uv run python examples/pipeline.py
"""

from __future__ import annotations

import asyncio
import os

from pydantic import BaseModel, Field

from operad import Configuration, Evaluator, Extractor, Pipeline, Planner


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


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=os.environ.get("OPERAD_LLAMACPP_MODEL", "default"),
        temperature=0.2,
        max_tokens=512,
    )


async def _main() -> None:
    cfg = _cfg()
    pipeline = Pipeline(
        Extractor(config=cfg, input=Request, output=Task),
        Planner(config=cfg, input=Task, output=Plan),
        Evaluator(config=cfg, input=Plan, output=Answer),
        input=Request,
        output=Answer,
    )
    await pipeline.abuild()
    result = await pipeline(Request(text="I want to learn Rust in a month on a budget."))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
