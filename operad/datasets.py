"""Typed `Dataset[In, Out]` — a reproducibility primitive.

Wraps `list[tuple[In, Out]]` with a stable content hash and cheap
NDJSON I/O. Not a heavyweight HF-Datasets analogue: no splits, no
streaming, no remote loaders. If you need that, build on top of this.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, Iterable, Iterator, TypeVar

from pydantic import BaseModel

from .utils.hashing import hash_json

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Dataset(Generic[In, Out]):
    """Typed `(input, expected-output)` rows with a content hash."""

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
        """Stable 16-hex-char content hash over rows + name + version."""
        payload = [
            {
                "input": a.model_dump(mode="json"),
                "output": b.model_dump(mode="json"),
            }
            for a, b in self._rows
        ]
        return hash_json(
            {"name": self.name, "version": self.version, "rows": payload}
        )

    def save(self, path: str | Path) -> None:
        """Write NDJSON: one `{"input": ..., "output": ...}` object per line."""
        p = Path(path)
        with p.open("w", encoding="utf-8") as f:
            for a, b in self._rows:
                line = json.dumps(
                    {
                        "input": a.model_dump(mode="json"),
                        "output": b.model_dump(mode="json"),
                    },
                    sort_keys=True,
                )
                f.write(line + "\n")

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
        p = Path(path)
        rows: list[tuple[In, Out]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rows.append(
                    (in_cls.model_validate(obj["input"]), out_cls.model_validate(obj["output"]))
                )
        return cls(rows, name=name, version=version)
