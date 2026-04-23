"""Two-branch Switch demo: a Router leaf picks a branch by typed Choice.

The Router classifies the incoming query as ``"greet"`` or ``"factoid"``;
the Switch dispatches to the matching Reasoner branch. Every edge is
typed; ``abuild()`` verifies that the Router's narrow ``Choice`` label
set covers every branch.

    uv run python examples/router_switch.py

Set ``OPERAD_LLAMACPP_HOST`` and ``OPERAD_LLAMACPP_MODEL`` to point at a
different llama-server endpoint or model.
"""

from __future__ import annotations

import asyncio
import os
from typing import Literal

from pydantic import BaseModel, Field

from operad import (
    Choice,
    Configuration,
    Reasoner,
    RouteInput,
    Router,
    Switch,
)


class Reply(BaseModel):
    text: str = Field(default="", description="The reply to the user.")


class Label(Choice[Literal["greet", "factoid"]]):
    pass


def _cfg(model: str) -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=model,
        temperature=0.3,
        max_tokens=256,
    )


async def _main() -> None:
    model = os.environ.get("OPERAD_LLAMACPP_MODEL", "default")
    cfg = _cfg(model)

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
        print(f"\n> {query}\n{reply.text}")


if __name__ == "__main__":
    asyncio.run(_main())
