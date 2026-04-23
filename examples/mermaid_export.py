"""Build a small composite and print its Mermaid graph.

Offline demo — no model server needed. ``build()`` traces the tree,
type-checks every edge, and produces an ``AgentGraph`` that
``to_mermaid`` renders as a flowchart.

    uv run python examples/mermaid_export.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad import Configuration, Extractor, Pipeline, Reasoner, to_mermaid


class Sentence(BaseModel):
    text: str = Field(default="", description="A free-form sentence.")


class Fact(BaseModel):
    subject: str = Field(default="", description="Who or what the sentence is about.")
    claim: str = Field(default="", description="What is asserted about the subject.")


class Verdict(BaseModel):
    reasoning: str = Field(default="", description="Why the fact is plausible or not.")
    plausible: bool = Field(default=False, description="Whether the claim seems plausible.")


async def _main() -> None:
    # Host intentionally unreachable — build() does not contact the model.
    cfg = Configuration(backend="llamacpp", host="127.0.0.1:0", model="offline")

    pipeline = Pipeline(
        Extractor(config=cfg, input=Sentence, output=Fact),
        Reasoner(config=cfg, input=Fact, output=Verdict),
        input=Sentence,
        output=Verdict,
    )
    await pipeline.abuild()
    print(to_mermaid(pipeline._graph))


if __name__ == "__main__":
    asyncio.run(_main())
