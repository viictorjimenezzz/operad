"""End-to-end smoke test against the hosted Anthropic API.

Opt-in: only runs when `OPERAD_INTEGRATION=anthropic`. Point at your key
and (optionally) override the model:

    OPERAD_INTEGRATION=anthropic \\
    ANTHROPIC_API_KEY=sk-ant-... \\
    OPERAD_ANTHROPIC_MODEL=claude-haiku-4-5 \\
    uv run pytest tests/integration/test_anthropic.py -v
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
        os.environ.get("OPERAD_INTEGRATION") != "anthropic",
        reason="set OPERAD_INTEGRATION=anthropic to enable",
    ),
]


class _Question(BaseModel):
    text: str = ""


class _Answer(BaseModel):
    answer: str = ""


async def test_leaf_against_real_anthropic() -> None:
    pytest.importorskip("strands.models.anthropic")

    api_key = os.environ["ANTHROPIC_API_KEY"]
    cfg = Configuration(
        backend="anthropic",
        model=os.environ.get("OPERAD_ANTHROPIC_MODEL", "claude-haiku-4-5"),
        api_key=api_key,
        temperature=0.0,
        max_tokens=128,
    )

    class Answerer(Agent[_Question, _Answer]):
        input = _Question
        output = _Answer
        task = "Answer the user's question concisely in the `answer` field."

    agent = Answerer(config=cfg)
    await agent.abuild()
    out = await agent(_Question(text="What is 2 + 2?"))
    assert isinstance(out, _Answer)
    assert out.answer.strip()
