"""Standalone ReAct: Reason -> Act -> Observe -> Evaluate.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Prints the Mermaid graph of the built architecture, then runs the
agent on a single goal.

    uv run python examples/react.py
"""

from __future__ import annotations

import asyncio

from operad import ReAct, Task, to_mermaid

from _config import local_config


async def _main() -> None:
    agent = ReAct(config=local_config(temperature=0.3, max_tokens=512))
    await agent.abuild()

    print("--- architecture ---")
    print(to_mermaid(agent._graph))
    print("--- run ---")

    answer = await agent(Task(goal="What is the sum of the first five primes?"))
    print(answer.response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
