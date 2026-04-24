"""Two-branch Switch demo: a Router leaf picks a branch by typed Choice.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

The Router classifies the incoming query as ``"greet"`` or ``"factoid"``;
the Switch dispatches to the matching Reasoner branch. Every edge is
typed; ``abuild()`` verifies that the Router's narrow ``Choice`` label
set covers every branch.

Run:
    uv run python examples/router_switch.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Literal

from pydantic import BaseModel, Field

from operad.core.config import Sampling
from operad.agents import (
    Choice,
    Reasoner,
    RouteInput,
    Router,
    Switch,
)

from _config import local_config, server_reachable

_SCRIPT = "router_switch.py"


class Reply(BaseModel):
    text: str = Field(default="", description="The reply to the user.")


class Label(Choice[Literal["greet", "factoid"]]):
    pass


async def main(offline: bool = False) -> None:
    cfg = local_config(sampling=Sampling(temperature=0.3, max_tokens=256))
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

    router = Router(
        config=cfg,
        input=RouteInput,
        output=Label,
        task=(
            "Pick 'greet' for a conversational greeting, "
            "'factoid' for a factual question."
        ),
    )

    greet = Reasoner(
        config=cfg, input=RouteInput, output=Reply,
        role="You are a warm, brief greeter.",
        task="Respond with a one-sentence greeting.",
    )
    factoid = Reasoner(
        config=cfg, input=RouteInput, output=Reply,
        role="You are a careful, terse encyclopedia.",
        task="Answer the factual question in one short sentence.",
    )

    root = Switch(
        router=router,
        branches={"greet": greet, "factoid": factoid},
        input=RouteInput,
        output=Reply,
    )
    await root.abuild()

    for query in ("Hello there!", "What is the capital of France?"):
        reply = await root(RouteInput(query=query))
        print(f"\n> {query}\n{reply.response.text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
