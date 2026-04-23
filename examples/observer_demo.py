"""Observer demo: a two-stage Pipeline logging every event to NDJSON.

    uv run python examples/observer_demo.py

Writes `/tmp/operad_observer_demo.jsonl` and prints it back.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from pydantic import BaseModel, Field

from operad import Agent, Configuration, JsonlObserver, Pipeline, observers


class Question(BaseModel):
    text: str = Field(default="", description="User question.")


class Draft(BaseModel):
    text: str = Field(default="", description="Intermediate draft answer.")


class Answer(BaseModel):
    text: str = Field(default="", description="Final answer.")


class _EchoLeaf(Agent):
    """A leaf that returns a fixed payload (no network needed for the demo)."""

    def __init__(self, *, config: Configuration, input, output, reply: str) -> None:
        super().__init__(config=config, input=input, output=output)
        self._reply = reply

    async def forward(self, x):  # type: ignore[override]
        return self.output(text=self._reply)


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model="demo",
    )


async def _main() -> None:
    cfg = _cfg()
    drafter = _EchoLeaf(config=cfg, input=Question, output=Draft, reply="draft")
    polisher = _EchoLeaf(config=cfg, input=Draft, output=Answer, reply="final")

    pipe = Pipeline(drafter, polisher, input=Question, output=Answer)
    await pipe.abuild()

    log_path = Path("/tmp/operad_observer_demo.jsonl")
    if log_path.exists():
        log_path.unlink()
    jo = JsonlObserver(log_path)
    observers.register(jo)

    try:
        out = await pipe(Question(text="how do observers work?"))
        print(f"result: {out.text}\n")
    finally:
        jo.close()
        observers.unregister(jo)

    print(f"--- {log_path} ---")
    print(log_path.read_text())


if __name__ == "__main__":
    asyncio.run(_main())
