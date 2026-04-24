"""Fan-out demo: run several specialized Reasoners on a shared prompt.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Each child of the ``Parallel`` composite runs concurrently against the
same local model server; the combine step folds their outputs into a
single report. Good minimal showcase of typed composition +
``abuild()`` + per-endpoint concurrency slots.

    uv run python examples/parallel.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad import Parallel
from operad.agents import Reasoner
from operad.runtime import set_limit

from _config import local_config


class Go(BaseModel):
    """Trigger input; each child's role/task carries the real instruction."""


class Answer(BaseModel):
    text: str = Field(default="", description="The agent's output, as plain text.")


class Report(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


TASKS: dict[str, tuple[str, str]] = {
    "poet":      ("You are a concise, evocative poet.",        "Write four lines on concurrency."),
    "engineer":  ("You are a pragmatic software engineer.",    "Explain async I/O in two sentences."),
    "historian": ("You are a careful historian of ideas.",     "Name one antecedent of the actor model."),
    "skeptic":   ("You are a rigorous skeptic.",               "List two failure modes of parallel agents."),
}


async def _main() -> None:
    cfg = local_config(temperature=0.7, max_tokens=512)
    set_limit(backend="llamacpp", host=cfg.host, concurrency=len(TASKS))

    children = {
        name: Reasoner(
            config=cfg, input=Go, output=Answer, role=role, task=task,
        )
        for name, (role, task) in TASKS.items()
    }

    root = Parallel(
        children,
        input=Go,
        output=Report,
        combine=lambda r: Report(answers={k: v.text for k, v in r.items()}),
    )
    await root.abuild()
    report = await root(Go())
    for name, answer in report.response.answers.items():
        print(f"\n{name}\n{'-' * 40}\n{answer}\n")


if __name__ == "__main__":
    asyncio.run(_main())
