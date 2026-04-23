"""Tests for ``Retriever``: pluggable async lookup, config-free build."""

from __future__ import annotations

import pytest

from operad import Hit, Hits, Query, Retriever


pytestmark = pytest.mark.asyncio


async def test_retriever_builds_without_config_and_returns_typed_hits() -> None:
    canned = [
        Hit(text="one", score=0.9, source="a"),
        Hit(text="two", score=0.4, source="b"),
    ]

    async def lookup(q: Query) -> list[Hit]:
        assert isinstance(q, Query)
        return canned

    r = Retriever(lookup=lookup)
    assert r.config is None
    await r.abuild()

    out = await r(Query(text="hello", k=2))
    assert isinstance(out, Hits)
    assert [h.text for h in out.items] == ["one", "two"]
    assert out.items[0].score == 0.9


async def test_retriever_passes_query_through() -> None:
    seen: list[Query] = []

    async def lookup(q: Query) -> list[Hit]:
        seen.append(q)
        return []

    r = await Retriever(lookup=lookup).abuild()
    seen.clear()  # discard the trace-time sentinel call
    await r(Query(text="foo", k=3))
    assert len(seen) == 1
    assert seen[0].text == "foo"
    assert seen[0].k == 3
