"""Observer demo: a two-stage Pipeline logging every event to NDJSON.

Runs offline — no model server required.

Writes `/tmp/operad_observer_demo.jsonl`, prints it back, and also
snapshots the run via `TraceObserver` to show the reproducibility
artefact. Note: `Agent.invoke` returns an `OperadOutput[Out]` envelope;
the typed payload is at `.response`.

Run:
    uv run python examples/observer_demo.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from operad import Agent, Configuration, Pipeline
from operad.runtime.observers import JsonlObserver, registry as observers
from operad.runtime.trace import TraceObserver

from _config import local_config


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


async def main(offline: bool = False) -> None:
    cfg = local_config(host="127.0.0.1:0", model="offline")
    drafter = _EchoLeaf(config=cfg, input=Question, output=Draft, reply="draft")
    polisher = _EchoLeaf(config=cfg, input=Draft, output=Answer, reply="final")

    pipe = Pipeline(drafter, polisher, input=Question, output=Answer)
    await pipe.abuild()

    log_path = Path("/tmp/operad_observer_demo.jsonl")
    if log_path.exists():
        log_path.unlink()
    jo = JsonlObserver(log_path)
    tracer = TraceObserver()
    observers.register(jo)
    observers.register(tracer)

    try:
        out = await pipe(Question(text="how do observers work?"))
        print(f"result: {out.response.text}\n")
    finally:
        jo.close()
        observers.unregister(jo)
        observers.unregister(tracer)

    print(f"--- {log_path} ---")
    print(log_path.read_text())

    trace = tracer.last()
    if trace is not None:
        print(f"--- trace: {len(trace.steps)} steps, run_id={trace.run_id} ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
