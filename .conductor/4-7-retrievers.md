# 4 · 7 — Retriever starter pack

**Addresses.** A-4 — `AutoResearcher` takes a `retriever` parameter
but there is no reference implementation. Users must wire their own
search backend before the algorithm is usable. See
[`../ISSUES.md`](../ISSUES.md) Group G.

**Depends on.** Nothing in Wave 4.

**Blocks.** 6-1 (demos showcase) — the stretch `research_arena` demo
needs a working retriever to be runnable end-to-end offline.

---

## Required reading

- `operad/agents/reasoning/components/` — existing leaf components,
  especially `retriever.py` (today a typed stub / interface).
- `operad/algorithms/auto_research.py` — how `retriever` is invoked.
- `operad/agents/reasoning/schemas.py` — shared `Query`,
  `Document`, `RetrievalResult` types (if they exist; otherwise add
  them in this brief).
- VISION §5 (components-vs-algorithms split) — retrievers are
  components (typed `Agent[Query, RetrievalResult]`), not algorithms.
- `tests/agents/test_retriever.py` if it exists; otherwise create one.

---

## Goal

Ship two concrete, offline-safe retrievers so `AutoResearcher` works
out of the box:

1. **`FakeRetriever`** — backed by a hardcoded corpus of `Document`s.
   Matches by exact-substring or Jaccard on token overlap; no external
   deps. Used by tests and the `research_arena` demo's offline mode.
2. **`BM25Retriever`** — a real BM25 implementation over a user-supplied
   corpus. One small dependency (`rank-bm25` or a ~50-line inline
   implementation). Demonstrates the full shape for users hooking
   vector stores or search APIs.

Both are `Agent[Query, RetrievalResult]` subclasses; both slot into
`AutoResearcher(retriever=...)` without further wiring.

## Scope

### Shared schemas

If not already present, add `operad/agents/reasoning/schemas.py`:

```python
from pydantic import BaseModel, Field

class Query(BaseModel):
    text: str = Field(description="The user's information need.")
    top_k: int = Field(default=5, description="Max documents to return.")

class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)

class RetrievalResult(BaseModel):
    documents: list[Document] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
```

Re-export from `operad.agents.reasoning.schemas` and
`operad.agents.reasoning`.

### `FakeRetriever`

`operad/agents/reasoning/components/fake_retriever.py`:

```python
class FakeRetriever(Agent[Query, RetrievalResult]):
    input = Query
    output = RetrievalResult
    role = "In-memory retriever over a fixed corpus."
    task = "Return top_k documents matching the query."

    def __init__(
        self, corpus: list[Document], *, scorer: Literal["jaccard","substring"]="jaccard"
    ) -> None:
        super().__init__(config=None, input=Query, output=RetrievalResult)
        self._corpus = corpus
        self._scorer = scorer

    async def forward(self, x: Query) -> RetrievalResult:
        scored = [(self._score(x.text, d.text), d) for d in self._corpus]
        scored.sort(key=lambda s: -s[0])
        top = scored[: x.top_k]
        return RetrievalResult(
            documents=[d for _, d in top],
            scores=[s for s, _ in top],
        )

    def _score(self, query: str, text: str) -> float:
        ...
```

No config needed — it's a pure-Python leaf (overrides `forward`, so
no strands wiring).

### `BM25Retriever`

`operad/agents/reasoning/components/bm25_retriever.py`:

```python
class BM25Retriever(Agent[Query, RetrievalResult]):
    input = Query
    output = RetrievalResult
    role = "BM25 retriever over a fixed corpus."
    task = "Return top_k documents ranked by BM25."

    def __init__(self, corpus: list[Document], *, k1: float = 1.5, b: float = 0.75) -> None:
        super().__init__(config=None, input=Query, output=RetrievalResult)
        # Tokenise each doc once; store IDF and term-frequency tables.
        ...

    async def forward(self, x: Query) -> RetrievalResult:
        ...
```

Prefer an inline ~50-line BM25 implementation over adding a new
dependency. Document the corpus update story in the docstring ("create
a new instance; corpus is immutable post-construction").

### Wire into `AutoResearcher`

Verify `AutoResearcher(retriever=...)` already accepts any
`Agent[Query, RetrievalResult]`. If the current type hints are
stricter (requiring a specific class), widen them. Update the
algorithm's docstring with a one-liner example:

```python
from operad.agents.reasoning.components import FakeRetriever, Document

ar = AutoResearcher(
    retriever=FakeRetriever(
        corpus=[Document(id="1", text="Paris is the capital of France.")]
    ),
    reasoner=...,
    critic=...,
)
```

### Public exports

Add both retrievers to `operad/agents/reasoning/components/__init__.py`
and `operad/agents/reasoning/__init__.py`.

---

## Verification

- Unit tests for `FakeRetriever`:
  - Empty corpus → empty `RetrievalResult`.
  - Exact-substring match scores > no-match.
  - `top_k=1` returns one document.
- Unit tests for `BM25Retriever`:
  - IDF computed correctly for a 3-document toy corpus.
  - Stop words don't dominate scoring.
  - Ranking matches a hand-computed example.
- Integration test: `AutoResearcher(retriever=FakeRetriever([...]))`
  builds and runs offline end-to-end with a `FakeLeaf` reasoner /
  critic. Asserts the retriever is actually called.
- `scripts/verify.sh` green.

---

## Out of scope

- Vector retrievers (Chroma, pgvector, Qdrant). Leave for a
  `VectorRetriever` brief when someone needs it; this brief just
  removes the A-4 blocker and models the correct component shape.
- Multi-query / HyDE / re-ranking. Those are higher-level algorithms
  composing retrievers — not in scope here.
- Embeddings interface. `BM25Retriever` is term-based on purpose.

---

## Design notes

- Retrievers are components, not algorithms (VISION §5). They subclass
  `Agent[Query, RetrievalResult]`, live under
  `operad/agents/reasoning/components/`, and override `forward` (so
  they skip strands wiring). Config is `None`.
- Do NOT convert these into Pydantic models; keep them
  Python classes with a `forward` method. Composition is by
  assigning into a composite's attribute.
- The corpus parameter is a list of `Document`s passed at construction
  time. No persistence, no reload. Users who want persistence can
  subclass.
