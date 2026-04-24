"""End-to-end smoke test against the hosted OpenAI API.

Opt-in: only runs when `OPERAD_INTEGRATION=openai`. Point at your key and
(optionally) override the model:

    OPERAD_INTEGRATION=openai \\
    OPENAI_API_KEY=sk-... \\
    OPERAD_OPENAI_MODEL=gpt-4o-mini \\
    uv run pytest tests/integration/test_openai.py -v
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
        os.environ.get("OPERAD_INTEGRATION") != "openai",
        reason="set OPERAD_INTEGRATION=openai to enable",
    ),
]


class _Greeting(BaseModel):
    text: str = ""


class _Echo(BaseModel):
    said: str = ""
    letters: int = 0


async def test_leaf_against_real_openai() -> None:
    pytest.importorskip("strands.models.openai")

    api_key = os.environ["OPENAI_API_KEY"]
    cfg = Configuration(
        backend="openai",
        model=os.environ.get("OPERAD_OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
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
