"""In-memory retriever over a fixed corpus.

``FakeRetriever`` is an offline-safe ``Agent[Query, Hits]`` that scores a
hardcoded corpus of ``Hit`` documents by Jaccard token overlap or
substring match. It overrides ``forward``, so no ``config`` is required
and no provider is contacted at build or invoke time.

Use it in tests, demos, and as the default retriever in the
``research_arena`` example. The corpus is fixed at construction; create a
new instance to update it.
"""

from __future__ import annotations

from typing import Literal

from ....core.agent import Agent
from ..schemas import Hit, Hits, Query


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if t}


class FakeRetriever(Agent[Query, Hits]):
    input = Query
    output = Hits

    role = "In-memory retriever over a fixed corpus."
    task = "Return top_k documents matching the query."

    def __init__(
        self,
        corpus: list[Hit],
        *,
        scorer: Literal["jaccard", "substring"] = "jaccard",
    ) -> None:
        super().__init__(config=None, input=Query, output=Hits)
        self._corpus = list(corpus)
        self._scorer = scorer

    async def forward(self, x: Query) -> Hits:  # type: ignore[override]
        scored = [(self._score(x.text, h.text), h) for h in self._corpus]
        scored.sort(key=lambda s: -s[0])
        top = scored[: x.top_k]
        return Hits(
            items=[
                Hit(text=h.text, score=score, source=h.source)
                for score, h in top
            ],
        )

    def _score(self, query: str, text: str) -> float:
        if self._scorer == "substring":
            q = query.lower()
            t = text.lower()
            if not q:
                return 0.0
            return 1.0 if q in t else 0.0
        q_tokens = _tokens(query)
        t_tokens = _tokens(text)
        if not q_tokens or not t_tokens:
            return 0.0
        intersection = q_tokens & t_tokens
        union = q_tokens | t_tokens
        return len(intersection) / len(union)


__all__ = ["FakeRetriever"]
