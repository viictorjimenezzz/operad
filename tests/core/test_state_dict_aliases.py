"""`Agent.state_dict` / `load_state_dict` mirror `state` / `load_state`."""

from __future__ import annotations

import pytest

from operad import Configuration

from ..conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_state_dict_returns_same_snapshot(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="describe")
    leaf.role = "critic"
    leaf.rules = ["be precise", "be brief"]

    via_canonical = leaf.state()
    via_alias = leaf.state_dict()

    assert via_alias.model_dump() == via_canonical.model_dump()


async def test_load_state_dict_matches_load_state(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, task="t1")
    a.role = "one"
    a.rules = ["r1"]
    snapshot = a.state()

    b = FakeLeaf(config=cfg, input=A, output=B, task="t2")
    b.role = "two"
    b.rules = ["r2", "r3"]

    b.load_state_dict(snapshot)

    assert b.role == a.role
    assert b.task == a.task
    assert b.rules == a.rules
    assert b.hash_content == a.hash_content


def test_both_names_in_dir() -> None:
    assert "state_dict" in dir(FakeLeaf)
    assert "load_state_dict" in dir(FakeLeaf)
