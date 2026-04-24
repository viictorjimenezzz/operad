"""Tests for `BM25Retriever`."""

from __future__ import annotations

import math

import pytest

from operad.agents.reasoning.components import BM25Retriever
from operad.agents.reasoning.schemas import Hit, Hits, Query


pytestmark = pytest.mark.asyncio


def _idf(n: int, n_q: int) -> float:
    return math.log((n - n_q + 0.5) / (n_q + 0.5) + 1.0)


async def test_idf_matches_hand_computed_values() -> None:
    corpus = [
        Hit(text="apple banana", score=0.0, source="d1"),
        Hit(text="apple cherry", score=0.0, source="d2"),
        Hit(text="durian", score=0.0, source="d3"),
    ]
    r = BM25Retriever(corpus=corpus)
    assert r._idf["apple"] == pytest.approx(_idf(3, 2))
    assert r._idf["banana"] == pytest.approx(_idf(3, 1))
    assert r._idf["durian"] == pytest.approx(_idf(3, 1))


async def test_common_terms_do_not_dominate_ranking() -> None:
    # "the" appears in every doc → low IDF; "specific" appears once → high IDF.
    corpus = [
        Hit(text="the the the specific", score=0.0, source="rare"),
        Hit(text="the the the the the", score=0.0, source="common1"),
        Hit(text="the the the the the the", score=0.0, source="common2"),
    ]
    r = await BM25Retriever(corpus=corpus).abuild()
    out = await r(Query(text="the specific", top_k=3))
    assert out.response.items[0].source == "rare"


async def test_ranking_matches_hand_computation() -> None:
    corpus = [
        Hit(text="alpha beta gamma", score=0.0, source="d1"),
        Hit(text="alpha alpha delta", score=0.0, source="d2"),
        Hit(text="epsilon zeta", score=0.0, source="d3"),
    ]
    r = await BM25Retriever(corpus=corpus, k1=1.5, b=0.75).abuild()
    out = await r(Query(text="alpha", top_k=3))
    items = out.response.items
    sources = [h.source for h in items]
    # d1 and d2 both contain 'alpha'; d3 has zero score.
    assert sources[2] == "d3"
    assert items[2].score == 0.0
    # d2 has higher term-frequency for 'alpha' than d1, so it ranks first.
    assert sources[0] == "d2"
    assert sources[1] == "d1"


async def test_empty_corpus_returns_empty_hits() -> None:
    r = await BM25Retriever(corpus=[]).abuild()
    out = await r(Query(text="anything", top_k=5))
    assert isinstance(out.response, Hits)
    assert out.response.items == []
