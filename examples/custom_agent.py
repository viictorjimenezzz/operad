"""User-defined Agent subclass: the minimal shape of a new leaf.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

``Agent[In, Out]`` is the one and only component contract. Subclass it,
set the class-level defaults (``input``, ``output``, ``role``, ``task``,
``rules``, ``examples``), and the framework handles prompt rendering,
structured output, and graph tracing.

    uv run python examples/custom_agent.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from operad import Agent, Example

from _config import local_config


class Joke(BaseModel):
    topic: str = Field(description="What the joke should be about.")


class Pun(BaseModel):
    setup: str = Field(default="", description="Short setup line.")
    punchline: str = Field(default="", description="The pun itself.")


class Punster(Agent[Joke, Pun]):
    """A leaf that writes one pun on a given topic."""

    input = Joke
    output = Pun

    role = "You are a quick-witted punster."
    task = "Given a topic, write one short pun: a setup followed by a punchline."
    rules = (
        "Keep it to two sentences total.",
        "Make the pun land on a single word with double meaning.",
    )
    examples = (
        Example[Joke, Pun](
            input=Joke(topic="atoms"),
            output=Pun(
                setup="Why don't scientists trust atoms?",
                punchline="Because they make up everything.",
            ),
        ),
    )


async def _main() -> None:
    agent = Punster(config=local_config(temperature=0.8, max_tokens=128))
    await agent.abuild()
    result = await agent(Joke(topic="databases"))
    print(result.response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
