# Feature · Typed `Dataset[In, Out]` + formalise `Metric.score_batch`

**Addresses.** E-13 (typed Dataset) + E-7 (formal score_batch) in
ISSUES.md. Combined in one brief because both touch `evaluate()`.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-7 and §E-13.
- `operad/eval.py`, `operad/metrics/base.py`, `operad/core/output.py`
  (for `hash_*` conventions).

---

## Proposal

### `Dataset[In, Out]`

A thin, typed wrapper around `list[tuple[In, Out]]` with a content
hash and cheap I/O. Not a heavyweight HF-style dataset — just a
reproducibility primitive.

```python
# operad/datasets.py (new module)
from typing import Generic, TypeVar, Iterable, Iterator
from pathlib import Path
from pydantic import BaseModel

from .core.output import hash_json

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Dataset(Generic[In, Out]):
    """Typed (input, expected-output) rows with a content hash.

    The hash_dataset property is stable across machines: it hashes
    the JSON dump of every row with sorted keys.
    """

    def __init__(
        self,
        rows: Iterable[tuple[In, Out]],
        *,
        name: str = "",
        version: str = "",
    ) -> None:
        self._rows: list[tuple[In, Out]] = list(rows)
        self.name = name
        self.version = version

    def __iter__(self) -> Iterator[tuple[In, Out]]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, i: int) -> tuple[In, Out]:
        return self._rows[i]

    @property
    def hash_dataset(self) -> str:
        """Stable 16-hex-char content hash."""
        payload = [
            {"input": a.model_dump(mode="json"), "output": b.model_dump(mode="json")}
            for a, b in self._rows
        ]
        return hash_json({"name": self.name, "version": self.version, "rows": payload})

    def save(self, path: str | Path) -> None:
        """NDJSON: one `{"input": ..., "output": ...}` per line."""
        ...

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        in_cls: type[In],
        out_cls: type[Out],
        name: str = "",
        version: str = "",
    ) -> "Dataset[In, Out]":
        ...
```

### `evaluate(...)` accepts `Dataset` or raw iterable

```python
# operad/eval.py — backwards compatible
async def evaluate(
    agent,
    dataset: Dataset[In, Out] | Iterable[tuple[In, Out]],
    metrics,
    *,
    concurrency: int = 4,
) -> EvalReport:
    ds = dataset if isinstance(dataset, Dataset) else Dataset(dataset)
    ...
```

`EvalReport` gains:

```python
class EvalReport(BaseModel):
    rows: list[dict[str, Any]]
    summary: dict[str, float]
    hash_dataset: str = ""        # NEW
    hash_graph: str = ""          # NEW — from agent._graph
    dataset_name: str = ""
    dataset_version: str = ""
```

Populate `hash_dataset` and `hash_graph` inside `evaluate`. These turn
`EvalReport` into a proper reproducibility record.

### Formal `Metric.score_batch`

Promote from `hasattr`-based dispatch in eval.py to a real Protocol
member with a default implementation:

```python
# operad/metrics/base.py
@runtime_checkable
class Metric(Protocol):
    name: str

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float: ...

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        return [await self.score(p, e) for p, e in pairs]
```

Protocols don't carry implementations, so `score_batch` lives on a
`MetricBase` abstract class that deterministic metrics inherit from
(or each metric implements the default trivially). Pick the simplest
approach — subclassable base class is fine.

Remove the `hasattr` path in `operad/eval.py`.

---

## Required tests

`tests/test_dataset.py`:
- Construct, iterate, `len`, `__getitem__`.
- `hash_dataset` stable across re-construction.
- `save` / `load` round-trip.

`tests/test_eval.py` (edit):
- `evaluate(agent, Dataset(...), metrics)` works.
- `EvalReport.hash_dataset` and `hash_graph` populate.
- Existing raw-list-of-tuples path still works.

`tests/test_metrics_base.py` (new, small):
- A metric without `score_batch` override still gets a working
  `score_batch` (via base class default).
- A metric overriding `score_batch` is used when available.

---

## Scope

- New: `operad/datasets.py`.
- Edit: `operad/eval.py` (accept `Dataset`, compute hashes, remove
  `hasattr`).
- Edit: `operad/metrics/base.py` (base class with default
  `score_batch`).
- Edit: every metric in `operad/metrics/*.py` to inherit or explicitly
  implement.
- New tests.
- Edit: `operad/__init__.py` re-exports.

Do NOT:
- Add HF-Datasets-style features (splits, streaming, remote loading).
- Break backwards compat: raw `list[tuple]` must still work.

---

## Acceptance

- `uv run pytest tests/` green.
- `Dataset` re-constructed from the same rows gives the same
  `hash_dataset`.
- `EvalReport` carries `hash_dataset` + `hash_graph` after evaluation.
- Static type checker (`ty` or `mypy`) no longer needs to guess at
  `score_batch` via hasattr.

---

## Watch-outs

- `Dataset` is a plain class (not Pydantic) — it owns typed Pydantic
  rows but isn't itself a Pydantic model, because Generic[In, Out]
  over Pydantic models is awkward for validation.
- Keep `name` / `version` loose strings. Don't invent a versioning
  scheme; let the caller manage them.
- `hash_dataset` depends on JSON dump order — make sure `sort_keys=True`
  (already the case in `hash_json`).
