from __future__ import annotations

import argparse
import asyncio

from pydantic import BaseModel, Field

from operad import Agent


class In(BaseModel):
    question: str = Field(description="The question to answer")


class Out(BaseModel):
    response: str = Field(description="A concise answer")


class Hello(Agent[In, Out]):
    input = In
    output = Out
    role = "You are a helpful assistant."
    task = "Answer the question concisely."


async def main(offline: bool) -> None:
    if offline:
        async def _fake(self, x: In) -> Out:
            return Out(response="Hello from operad!")
        Hello.forward = _fake  # type: ignore[method-assign]

    agent = Hello()
    await agent.abuild()
    out = await agent(In(question="What is operad?"))
    print(out.response.response)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true")
    asyncio.run(main(p.parse_args().offline))
