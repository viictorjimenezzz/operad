"""`MemoryStore[T]` — a typed, append-only-ish store of Pydantic records.

A plain data primitive: not an ``Agent``, not an algorithm. v1 is an
in-memory list with optional NDJSON persistence to a caller-chosen
path. No embeddings, no vector search, no SQLite — the point is the
typed surface, not the storage engine.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MemoryStore(Generic[T]):
    """In-memory typed store with optional NDJSON persistence.

    Construct with a Pydantic ``schema`` and, optionally, a ``path`` to
    an NDJSON file. When a path is supplied, existing lines are loaded
    at construction and every ``add`` eagerly appends a new line. Call
    ``flush()`` to rewrite the file from the current in-memory list if
    items have been mutated in place.
    """

    def __init__(self, schema: type[T], path: Path | None = None) -> None:
        self.schema = schema
        self.path = path
        self._items: list[T] = []

        if path is not None and path.exists():
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    self._items.append(schema.model_validate_json(line))

    def add(self, item: T) -> None:
        """Append one item. Raises ``TypeError`` if it is not the schema."""
        if not isinstance(item, self.schema):
            raise TypeError(
                f"MemoryStore expected {self.schema.__name__}, "
                f"got {type(item).__name__}"
            )
        self._items.append(item)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(item.model_dump_json())
                fh.write("\n")

    def all(self) -> list[T]:
        """Return a shallow copy of every stored item."""
        return list(self._items)

    def filter(self, pred: Callable[[T], bool]) -> list[T]:
        """Return every stored item for which `pred` is truthy."""
        return [item for item in self._items if pred(item)]

    def flush(self) -> None:
        """Rewrite the NDJSON file from the current in-memory list.

        No-op when no path was configured. Use after mutating items in
        place or after bulk operations that bypassed ``add``.
        """
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for item in self._items:
                fh.write(item.model_dump_json())
                fh.write("\n")
