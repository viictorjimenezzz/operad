# Phase 2 · Stream I — Memory domain

**Goal.** Ship `operad/agents/memory/` with extractor leaves and a
minimal typed memory store. Mirror the shape of
`operad/agents/reasoning/`.

**Owner.** One agent.
**Depends on.** Stream E (`Retriever` composes well with
`MemoryStore`).
**Addresses:** C-4 (memory sub-domain).

---

## Scope

### Files you will create
- `operad/agents/memory/__init__.py`
- `operad/agents/memory/components/__init__.py`
- `operad/agents/memory/components/belief_extractor.py`
- `operad/agents/memory/components/user_model_extractor.py`
- `operad/agents/memory/components/episodic_summarizer.py`
- `operad/agents/memory/store.py` — `MemoryStore[T]` plain class.
- `tests/test_memory_components.py`, `test_memory_store.py`.
- `examples/memory_demo.py`.

### Files you will edit
- `operad/agents/__init__.py` — re-exports.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- Other domains, core, runtime.

---

## Design direction

### Typed shapes

```python
class Belief(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = ""

class Beliefs(BaseModel):
    items: list[Belief]

class Turn(BaseModel):
    speaker: Literal["user", "agent"]
    text: str
    timestamp: float | None = None

class Conversation(BaseModel):
    turns: list[Turn]

class UserModel(BaseModel):
    attributes: dict[str, str] = Field(default_factory=dict)

class Summary(BaseModel):
    title: str
    text: str
```

### Leaves

- **`BeliefExtractor(Agent[Conversation, Beliefs])`** — reads recent
  turns, emits typed beliefs.
- **`UserModelExtractor(Agent[Conversation, UserModel])`** — maintains
  a flat dict of known user attributes.
- **`EpisodicSummarizer(Agent[Conversation, Summary])`** — rolls a
  session into a title + narrative summary.

Standard default-forward leaf pattern with `role` / `task` / `rules`
at class level. Ship one `Example(...)` per leaf.

### `MemoryStore[T]`

Plain class — not an Agent, not an algorithm (it's a data primitive).

```python
class MemoryStore(Generic[T]):
    def __init__(self, schema: type[T], path: Path | None = None) -> None: ...

    def add(self, item: T) -> None: ...
    def all(self) -> list[T]: ...
    def filter(self, pred: Callable[[T], bool]) -> list[T]: ...
    def flush(self) -> None: ...   # write NDJSON to path if set
```

In-memory list of `T` instances. If `path` is provided, append an
NDJSON line on every `add` and load existing lines on init. No
embeddings, no vector search, no SQLite in v1. The point is the typed
surface, not the storage engine.

---

## Tests

- `BeliefExtractor` with FakeLeaf produces a typed `Beliefs` list.
- `MemoryStore` add / filter / all round-trip.
- `MemoryStore` with a path: add → new instance reads prior items.
- Type safety: adding a non-`T` raises.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/memory_demo.py` shows belief extraction over two turns
  and a filter query like
  `store.filter(lambda b: b.confidence > 0.7)`.

---

## Watch-outs

- Do NOT add embeddings, vector search, or SQLite yet. v1 is in-memory
  list + NDJSON append. Sell the typed surface first; optimise later.
- `MemoryStore` is a plain class; don't try to make it an Agent.
- Persisted files are user state — don't write them under `.git/` or
  `.context/` by default. The caller chooses the path.
