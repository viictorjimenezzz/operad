"""End-to-end smoke test against the hosted Gemini API.

Opt-in: only runs when `OPERAD_INTEGRATION=gemini`.

    OPERAD_INTEGRATION=gemini \\
    GEMINI_API_KEY=... \\
    OPERAD_GEMINI_MODEL=gemini-1.5-flash \\
    uv run pytest tests/integration/test_gemini.py -v
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
        os.environ.get("OPERAD_INTEGRATION") != "gemini",
        reason="set OPERAD_INTEGRATION=gemini to enable",
    ),
]


class _Greeting(BaseModel):
    text: str = ""


class _Echo(BaseModel):
    said: str = ""


async def test_leaf_against_real_gemini() -> None:
    pytest.importorskip("strands.models.gemini")

    api_key = os.environ["GEMINI_API_KEY"]
    cfg = Configuration(
        backend="gemini",
        model=os.environ.get("OPERAD_GEMINI_MODEL", "gemini-1.5-flash"),
        api_key=api_key,
        temperature=0.0,
        max_tokens=64,
    )

    class Echoer(Agent[_Greeting, _Echo]):
        input = _Greeting
        output = _Echo
        task = "Echo the user's input back in the `said` field."

    agent = Echoer(config=cfg)
    await agent.abuild()
    out = await agent(_Greeting(text="hello"))
    assert isinstance(out, _Echo)
    assert out.said
