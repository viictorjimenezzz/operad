"""End-to-end smoke test against a real Ollama server.

Opt-in: only runs when `OPERAD_INTEGRATION=ollama`. Use env vars to point
the test at your server:

    OPERAD_INTEGRATION=ollama \\
    OPERAD_OLLAMA_HOST=127.0.0.1:11434 \\
    OPERAD_OLLAMA_MODEL=llama3.2 \\
    uv run pytest tests/integration/test_ollama.py -v
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration
from operad.core.config import Sampling


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "ollama",
        reason="set OPERAD_INTEGRATION=ollama to enable",
    ),
]


class _Greeting(BaseModel):
    text: str = ""


class _Echo(BaseModel):
    said: str = ""
    letters: int = 0


async def test_leaf_against_real_ollama_server() -> None:
    pytest.importorskip("strands.models.ollama")

    cfg = Configuration(
        backend="ollama",
        host=os.environ.get("OPERAD_OLLAMA_HOST", "127.0.0.1:11434"),
        model=os.environ.get("OPERAD_OLLAMA_MODEL", "llama3.2"),
        sampling=Sampling(temperature=0.0, max_tokens=64),
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
    assert out.said
