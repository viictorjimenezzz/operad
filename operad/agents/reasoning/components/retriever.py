"""Retriever leaf: pluggable async lookup with typed hits.

``Retriever`` is not an LLM call by default — it overrides ``forward`` to
invoke a user-supplied async ``lookup`` callable. Because the forward is
overridden, no ``config`` is required and ``strands`` is never wired up at
build time. This keeps the leaf fully offline-testable and makes it the
natural seam for plugging in a vector store, a keyword index, or a mock
fixture.

Subclass to swap the I/O types for a domain (e.g. ``MyRetriever(Query,
CodeHits)``) while keeping the same dispatch skeleton.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from ....core.agent import Agent, Example
from ..schemas import Hit, Hits, Query


class Retriever(Agent[Query, Hits]):
    input = Query
    output = Hits

    role = "You retrieve the most relevant items for a query."
    task = "Return the hits sorted by relevance, with scores."
    rules = (
        "Prefer precision over recall.",
        "Discard hits below the relevance threshold.",
    )
    examples = (
        Example[Query, Hits](
            input=Query(text="what is TCP?", k=2),
            output=Hits(
                items=[
                    Hit(text="TCP is a reliable transport protocol.",
                        score=0.92, source="rfc793"),
                    Hit(text="TCP uses a three-way handshake.",
                        score=0.81, source="rfc793"),
                ],
            ),
        ),
    )

    def __init__(
        self,
        *,
        lookup: Callable[[Query], Awaitable[list[Hit]]],
        input: type[BaseModel] = Query,
        output: type[BaseModel] = Hits,
    ) -> None:
        super().__init__(config=None, input=input, output=output)
        self._lookup = lookup

    async def forward(self, x: Query) -> Hits:  # type: ignore[override]
        items = await self._lookup(x)
        return Hits(items=list(items))


__all__ = ["Hit", "Hits", "Query", "Retriever"]
