"""Cassette-based replay: proof of life.

Exercises the ``cassette`` fixture against a default-forward leaf. The
committed JSONL file under ``tests/cassettes/`` carries a hand-seeded
entry so the offline suite passes on a fresh checkout without any
recording step.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from operad import Agent
from operad.utils.cassette import CassetteMiss

from .conftest import cfg as cfg_fixture  # noqa: F401  (used as fixture)


class DemoIn(BaseModel):
    """Cassette demo input."""

    question: str = Field(default="", description="user question")


class DemoOut(BaseModel):
    """Cassette demo output."""

    answer: str = Field(default="", description="model answer")


class DemoLeaf(Agent[DemoIn, DemoOut]):
    input = DemoIn
    output = DemoOut
    role = "You are a terse demo assistant."
    task = "Answer the question in one short sentence."


CASSETTE_DIR = Path(__file__).parent / "cassettes"


@pytest.mark.asyncio
async def test_cassette_replays_recorded_answer(cassette, cfg) -> None:
    leaf = await DemoLeaf(config=cfg).abuild()
    out = (await leaf(DemoIn(question="what is 2+2?"))).response
    assert isinstance(out, DemoOut)
    assert out.answer == "four"


@pytest.mark.asyncio
async def test_cassette_miss_raises(cfg, tmp_path) -> None:
    from operad.utils.cassette import cassette_context

    empty = tmp_path / "empty.jsonl"
    with cassette_context(empty, mode="replay"):
        leaf = await DemoLeaf(config=cfg).abuild()
        with pytest.raises(CassetteMiss) as exc:
            await leaf(DemoIn(question="never recorded"))
    assert "missing cassette key" in str(exc.value)


def test_cassette_file_has_no_secrets() -> None:
    """Guard: committed cassette files store hashes only, not prompts."""
    for p in CASSETTE_DIR.glob("*.jsonl"):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            assert set(entry.keys()) == {
                "key",
                "hash_model",
                "hash_prompt",
                "hash_input",
                "response_json",
                "recorded_at",
            }, f"unexpected fields in {p}: {sorted(entry.keys())}"
