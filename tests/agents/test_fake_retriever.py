"""Tests for `FakeRetriever`."""

from __future__ import annotations

import pytest

from operad.agents.reasoning.components import FakeRetriever
from operad.agents.reasoning.schemas import Hit, Hits, Query


pytestmark = pytest.mark.asyncio


async def test_empty_corpus_returns_empty_hits() -> None:
    r = await FakeRetriever(corpus=[]).abuild()
    out = await r(Query(text="anything"))
    assert isinstance(out.response, Hits)
    assert out.response.items == []


async def test_substring_match_outscores_no_match() -> None:
    corpus = [
        Hit(text="Paris is the capital of France.", score=0.0, source="a"),
        Hit(text="Bananas are yellow.", score=0.0, source="b"),
    ]
    r = await FakeRetriever(corpus=corpus, scorer="substring").abuild()
    out = await r(Query(text="capital of france", top_k=2))
    items = out.response.items
    assert items[0].source == "a"
    assert items[0].score == 1.0
    assert items[1].score == 0.0


async def test_jaccard_ranks_overlap_higher() -> None:
    corpus = [
        Hit(text="cats and dogs", score=0.0, source="a"),
        Hit(text="elephants are big", score=0.0, source="b"),
    ]
    r = await FakeRetriever(corpus=corpus, scorer="jaccard").abuild()
    out = await r(Query(text="cats", top_k=2))
    items = out.response.items
    assert items[0].source == "a"
    assert items[0].score > items[1].score


async def test_top_k_one_returns_single_hit() -> None:
    corpus = [
        Hit(text=f"doc {i}", score=0.0, source=f"s{i}") for i in range(5)
    ]
    r = await FakeRetriever(corpus=corpus).abuild()
    out = await r(Query(text="doc 3", top_k=1))
    assert len(out.response.items) == 1


async def test_jaccard_empty_query_scores_zero() -> None:
    corpus = [Hit(text="something", score=0.0, source="a")]
    r = await FakeRetriever(corpus=corpus, scorer="jaccard").abuild()
    out = await r(Query(text="", top_k=1))
    assert out.response.items[0].score == 0.0
