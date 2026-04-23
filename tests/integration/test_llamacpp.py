"""End-to-end smoke test against a real llama-server.

Opt-in: only runs when `OPERAD_INTEGRATION=llamacpp`. Use env vars to
point the test at your server:

    OPERAD_INTEGRATION=llamacpp \\
    OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \\
    OPERAD_LLAMACPP_MODEL=qwen2.5-7b-instruct \\
    uv run pytest tests/integration -v

This is the single proof that `Configuration` is no longer inert: the
library builds an `Agent`, sends one request, and parses structured output.
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "llamacpp",
        reason="set OPERAD_INTEGRATION=llamacpp to enable",
    ),
]


class _Greeting(BaseModel):
    text: str = ""


class _Echo(BaseModel):
    said: str = ""
    letters: int = 0


async def test_leaf_against_real_llamacpp_server() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=os.environ.get("OPERAD_LLAMACPP_MODEL", "default"),
        temperature=0.0,
        max_tokens=64,
    )

    class Echoer(Agent[_Greeting, _Echo]):
        input = _Greeting
        output = _Echo
        task = (
            "Echo the user's input back in the `said` field. "
            "Count its characters (excluding whitespace) into `letters`."
        )

    agent = Echoer(config=cfg)
    await agent.abuild()
    out = await agent(_Greeting(text="hello"))
    assert isinstance(out, _Echo)
    assert out.said  # the model must have populated it
