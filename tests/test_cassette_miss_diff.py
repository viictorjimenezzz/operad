"""Cassette-miss diff: the miss message names the drifting segment.

When a cassette lookup misses, `CassetteMiss` should expose per-segment
match counts against the stored entries and render a diff block naming
the most likely drift cause (prompt / input / config).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.utils.cassette import CassetteMiss, cassette_context
from operad.utils.hashing import hash_input, hash_model, hash_prompt


class MissIn(BaseModel):
    question: str = Field(default="", description="user question")


class MissOut(BaseModel):
    answer: str = Field(default="", description="model answer")


class MissLeaf(Agent[MissIn, MissOut]):
    input = MissIn
    output = MissOut
    role = "You are a terse assistant."
    task = "Answer in one short sentence."


def _seed(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, sort_keys=True) + "\n")


async def _segment_hashes(
    leaf: MissLeaf, cfg: Configuration, x: MissIn
) -> tuple[str, str, str]:
    system = leaf.format_system_message()
    user = leaf.format_user_message(x)
    return hash_model(cfg), hash_prompt(system, user), hash_input(x)


@pytest.mark.asyncio
async def test_prompt_drift_miss(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")
    h_m, h_p, h_i = await _segment_hashes(leaf, cfg, x)

    path = tmp_path / "prompt_drift.jsonl"
    _seed(
        path,
        [
            {
                "key": "seed1",
                "hash_model": h_m,
                "hash_prompt": "different_prompt_hash",
                "hash_input": h_i,
                "response_json": "{}",
                "recorded_at": 0.0,
            }
        ],
    )

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert exc.matches["hash_model"] == 1
    assert exc.matches["hash_input"] == 1
    assert exc.matches["hash_prompt"] == 0
    msg = str(exc)
    assert "prompt drift" in msg
    assert f"OPERAD_CASSETTE=record uv run pytest {path} -v" in msg


@pytest.mark.asyncio
async def test_input_drift_miss(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")
    h_m, h_p, h_i = await _segment_hashes(leaf, cfg, x)

    path = tmp_path / "input_drift.jsonl"
    _seed(
        path,
        [
            {
                "key": "seed1",
                "hash_model": h_m,
                "hash_prompt": h_p,
                "hash_input": "different_input_hash",
                "response_json": "{}",
                "recorded_at": 0.0,
            }
        ],
    )

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert exc.matches["hash_model"] == 1
    assert exc.matches["hash_prompt"] == 1
    assert exc.matches["hash_input"] == 0
    assert "input drift" in str(exc)


@pytest.mark.asyncio
async def test_config_drift_miss(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")
    h_m, h_p, h_i = await _segment_hashes(leaf, cfg, x)

    path = tmp_path / "config_drift.jsonl"
    _seed(
        path,
        [
            {
                "key": "seed1",
                "hash_model": "different_model_hash",
                "hash_prompt": h_p,
                "hash_input": h_i,
                "response_json": "{}",
                "recorded_at": 0.0,
            }
        ],
    )

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert exc.matches["hash_prompt"] == 1
    assert exc.matches["hash_input"] == 1
    assert exc.matches["hash_model"] == 0
    assert "config drift" in str(exc)


@pytest.mark.asyncio
async def test_multiple_drift_miss(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")
    h_m, h_p, h_i = await _segment_hashes(leaf, cfg, x)

    path = tmp_path / "multi_drift.jsonl"
    _seed(
        path,
        [
            {
                "key": "seed1",
                "hash_model": h_m,
                "hash_prompt": "different_prompt_hash",
                "hash_input": "different_input_hash",
                "response_json": "{}",
                "recorded_at": 0.0,
            }
        ],
    )

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert exc.matches["hash_model"] == 1
    assert exc.matches["hash_prompt"] == 0
    assert exc.matches["hash_input"] == 0
    assert "multiple segments drifted" in str(exc)


@pytest.mark.asyncio
async def test_empty_cassette_miss(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")

    path = tmp_path / "does_not_exist.jsonl"

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert exc.matches == {"hash_model": 0, "hash_prompt": 0, "hash_input": 0}
    assert "Cassette is empty" in str(exc)


@pytest.mark.asyncio
async def test_programmatic_access(cfg, tmp_path) -> None:
    leaf = await MissLeaf(config=cfg).abuild()
    x = MissIn(question="q")

    path = tmp_path / "prog.jsonl"
    _seed(path, [])

    with cassette_context(path, mode="replay"):
        with pytest.raises(CassetteMiss) as excinfo:
            await leaf(x)

    exc = excinfo.value
    assert isinstance(exc, KeyError)
    assert isinstance(exc.matches, dict)
    assert set(exc.matches.keys()) == {"hash_model", "hash_prompt", "hash_input"}
    assert isinstance(exc.key, str) and len(exc.key) == 16
    assert isinstance(exc.hash_model, str)
    assert isinstance(exc.hash_prompt, str)
    assert isinstance(exc.hash_input, str)
    assert exc.path == path
