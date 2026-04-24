"""BM25 retriever over a fixed corpus.

``BM25Retriever`` is an offline-safe ``Agent[Query, Hits]`` that ranks a
hardcoded corpus of ``Hit`` documents by Okapi BM25. The implementation
is inline (~50 lines) and adds no dependencies; it tokenizes by
lowercasing and splitting on whitespace.

Use it as the reference shape for users wiring real search backends. The
corpus is fixed at construction; create a new instance to update it.
"""

from __future__ import annotations

import math

from ....core.agent import Agent
from ..schemas import Hit, Hits, Query


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t]


class BM25Retriever(Agent[Query, Hits]):
    input = Query
    output = Hits

    role = "BM25 retriever over a fixed corpus."
    task = "Return top_k documents ranked by BM25."

    def __init__(
        self,
        corpus: list[Hit],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        super().__init__(config=None, input=Query, output=Hits)
        self._corpus = list(corpus)
        self._k1 = k1
        self._b = b

        self._doc_tokens: list[list[str]] = [_tokenize(h.text) for h in self._corpus]
        self._doc_lens: list[int] = [len(toks) for toks in self._doc_tokens]
        self._avgdl: float = (
            sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0
        )

        n = len(self._doc_tokens)
        df: dict[str, int] = {}
        for toks in self._doc_tokens:
            for term in set(toks):
                df[term] = df.get(term, 0) + 1
        self._idf: dict[str, float] = {
            term: math.log((n - n_q + 0.5) / (n_q + 0.5) + 1.0)
            for term, n_q in df.items()
        }

        self._tf: list[dict[str, int]] = []
        for toks in self._doc_tokens:
            counts: dict[str, int] = {}
            for term in toks:
                counts[term] = counts.get(term, 0) + 1
            self._tf.append(counts)

    async def forward(self, x: Query) -> Hits:  # type: ignore[override]
        q_terms = _tokenize(x.text)
        scored: list[tuple[float, Hit]] = []
        for i, doc in enumerate(self._corpus):
            scored.append((self._score(q_terms, i), doc))
        scored.sort(key=lambda s: -s[0])
        top = scored[: x.top_k]
        return Hits(
            items=[
                Hit(text=h.text, score=score, source=h.source)
                for score, h in top
            ],
        )

    def _score(self, q_terms: list[str], doc_idx: int) -> float:
        if self._avgdl == 0.0:
            return 0.0
        dl = self._doc_lens[doc_idx]
        tf = self._tf[doc_idx]
        score = 0.0
        for term in q_terms:
            f = tf.get(term, 0)
            if f == 0:
                continue
            idf = self._idf.get(term, 0.0)
            denom = f + self._k1 * (1.0 - self._b + self._b * dl / self._avgdl)
            score += idf * (f * (self._k1 + 1.0)) / denom
        return score


__all__ = ["BM25Retriever"]
