"""Standalone ReAct: Reason -> Act -> Observe -> Evaluate.

Prints the Mermaid graph of the built architecture, then runs the
agent on a single goal.

Requires a local llama-server at ``$OPERAD_LLAMACPP_HOST`` (default
``127.0.0.1:8080``). Set ``OPERAD_LLAMACPP_MODEL`` to pick a model.

    uv run python examples/react.py
"""

from __future__ import annotations

import asyncio
import os

from operad import Configuration, ReAct, Task, to_mermaid


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=os.environ.get("OPERAD_LLAMACPP_MODEL", "default"),
        temperature=0.3,
        max_tokens=512,
    )


async def _main() -> None:
    agent = ReAct(config=_cfg())
    await agent.abuild()

    print("--- architecture ---")
    print(to_mermaid(agent._graph))
    print("--- run ---")

    answer = await agent(Task(goal="What is the sum of the first five primes?"))
    print(answer.response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
