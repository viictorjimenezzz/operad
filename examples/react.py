"""Standalone ReAct: Reason -> Act -> Observe -> Evaluate.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Prints the Mermaid graph of the built architecture, then runs the
agent on a single goal.

Run:
    uv run python examples/react.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from operad.agents import ReAct, Task
from operad.core.graph import to_mermaid

from _config import local_config, server_reachable

_SCRIPT = "react.py"


async def main(offline: bool = False) -> None:
    cfg = local_config(temperature=0.3, max_tokens=512)
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
    agent = ReAct(config=cfg)
    await agent.abuild()

    print("--- architecture ---")
    print(to_mermaid(agent._graph))
    print("--- run ---")

    answer = await agent(Task(goal="What is the sum of the first five primes?"))
    print(answer.response.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
