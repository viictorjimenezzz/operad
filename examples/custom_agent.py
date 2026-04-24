"""User-defined Agent subclass: the minimal shape of a new leaf.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

``Agent[In, Out]`` is the one and only component contract. Subclass it,
set the class-level defaults (``input``, ``output``, ``role``, ``task``,
``rules``, ``examples``), and the framework handles prompt rendering,
structured output, and graph tracing.

Run:
    uv run python examples/custom_agent.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from operad import Agent, Configuration, Example

from _config import local_config, server_reachable


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


class _OfflinePunster(Agent[Joke, Pun]):
    """Offline stub matching Punster's typed contract.

    ``build()`` traces with a ``model_construct()`` sentinel whose fields
    are not populated, so ``forward`` must not read from ``x`` at all.
    """

    input = Joke
    output = Pun

    async def forward(self, x: Joke) -> Pun:  # type: ignore[override]
        return Pun.model_construct(
            setup="Why did the database break up?",
            punchline="It had too many unresolved references.",
        )


async def main(offline: bool = False) -> None:
    script = "custom_agent.py"
    if offline:
        cfg = Configuration(
            backend="llamacpp", host="127.0.0.1:0", model="offline",
        )
        agent: Agent[Joke, Pun] = _OfflinePunster(config=cfg)
    else:
        cfg = local_config(temperature=0.8, max_tokens=128)
        print(f"[{script}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
        if not server_reachable(cfg.host):
            print(
                f"[{script}] cannot reach {cfg.host} — start llama-server or pass --offline",
                file=sys.stderr,
            )
            raise SystemExit(1)
        agent = Punster(config=cfg)

    await agent.abuild()
    result = await agent(Joke(topic="databases"))
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
