"""Federated demo: one graph, two backends, independent slot budgets.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL. Also needs
OPENAI_API_KEY for the hosted leg; override its model with
OPERAD_OPENAI_MODEL (default ``gpt-4o-mini``).

A ``Parallel`` fans the same ``Post`` out to three children: two cheap
local classifiers on llamacpp and one hosted synthesiser on OpenAI.
The combine step folds their outputs into a single ``Report``. This
showcases the slot registry keying on ``(backend, host)``: the two
llamacpp calls share one semaphore while the OpenAI call runs on an
independent one (see ``operad/runtime/slots.py`` line 37-38). Call
``set_limit`` before ``abuild()`` — semaphores cache on first use.

    uv run python examples/federated.py

Costs money on the OpenAI side.
"""

from __future__ import annotations

import asyncio
import os
from typing import Literal

from pydantic import BaseModel, Field

from operad import Classifier, Configuration, Parallel, Reasoner, set_limit

from _config import local_config


class Post(BaseModel):
    text: str = Field(description="The post's body text to analyse.")


class Sentiment(BaseModel):
    label: Literal["positive", "neutral", "negative"] = Field(
        description="Overall sentiment of the post."
    )


class Topics(BaseModel):
    items: list[str] = Field(
        default_factory=list,
        description="Up to five short topic tags drawn from the post.",
    )


class PostSummary(BaseModel):
    headline: str = Field(description="A single-sentence headline for the post.")


class Report(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    topics: list[str]
    headline: str


SAMPLE = (
    "Shipped the new billing flow today. Support tickets on invoices "
    "dropped overnight and the on-call rotation finally got some sleep."
)


async def _main() -> None:
    local = local_config(temperature=0.0)
    hosted = Configuration(
        backend="openai",
        model=os.environ.get("OPERAD_OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0.3,
    )

    set_limit(backend="llamacpp", host=local.host, limit=8)
    set_limit(backend="openai", limit=2)

    root = Parallel(
        {
            "sentiment": Classifier(config=local, input=Post, output=Sentiment),
            "topics": Classifier(config=local, input=Post, output=Topics),
            "summary": Reasoner(config=hosted, input=Post, output=PostSummary),
        },
        input=Post,
        output=Report,
        combine=lambda r: Report(
            sentiment=r["sentiment"].label,
            topics=r["topics"].items,
            headline=r["summary"].headline,
        ),
    )
    await root.abuild()
    report = await root(Post(text=SAMPLE))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
