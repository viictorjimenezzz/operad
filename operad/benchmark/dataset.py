"""Typed `Dataset[In, Out]` — a list of `Entry[In, Out]` with a content hash."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, Iterable, Iterator, TypeVar

from pydantic import BaseModel, ValidationError

from ..metrics.base import Metric
from ..utils.hashing import hash_json
from .entry import Entry

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


def _validate_row(
    entry: "Entry",
    index: int,
    in_cls: type[BaseModel] | None,
    out_cls: type[BaseModel] | None,
) -> None:
    """Validate one Entry's input/expected_output; raise ValueError on failure.

    When ``in_cls`` / ``out_cls`` are provided, enforce the schemas via
    ``model_validate``. Otherwise, round-trip through
    ``model_dump(mode="json")`` to catch malformed Pydantic state early
    (e.g. tuples that bypassed field validators via `model_construct`).
    """
    try:
        if in_cls is not None:
            in_cls.model_validate(entry.input)
        else:
            entry.input.model_dump(mode="json")
    except (ValidationError, AttributeError, TypeError) as err:
        raise ValueError(
            f"Dataset row {index}: input failed validation: {err}"
        ) from err
    if entry.expected_output is None:
        return
    try:
        if out_cls is not None:
            out_cls.model_validate(entry.expected_output)
        else:
            entry.expected_output.model_dump(mode="json")
    except (ValidationError, AttributeError, TypeError) as err:
        raise ValueError(
            f"Dataset row {index}: expected_output failed validation: {err}"
        ) from err


class Dataset(Generic[In, Out]):
    """Typed benchmark dataset with a stable content hash."""

    def __init__(
        self,
        entries: Iterable[Entry[In, Out]] | Iterable[tuple[In, Out]],
        *,
        name: str = "",
        version: str = "",
        in_cls: type[In] | None = None,
        out_cls: type[Out] | None = None,
    ) -> None:
        coerced: list[Entry[In, Out]] = []
        for i, e in enumerate(entries):
            if isinstance(e, Entry):
                entry = e
            else:
                try:
                    inp, exp = e
                except (TypeError, ValueError) as err:
                    raise ValueError(
                        f"Dataset row {i}: expected Entry or (input, "
                        f"expected_output) tuple, got {type(e).__name__}"
                    ) from err
                try:
                    entry = Entry(input=inp, expected_output=exp)
                except ValidationError as err:
                    raise ValueError(
                        f"Dataset row {i}: could not construct Entry: {err}"
                    ) from err
            _validate_row(entry, i, in_cls, out_cls)
            coerced.append(entry)
        self._entries: list[Entry[In, Out]] = coerced
        self.name = name
        self.version = version

    def __iter__(self) -> Iterator[Entry[In, Out]]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, i: int) -> Entry[In, Out]:
        return self._entries[i]

    def _row_payload(self, entry: Entry[In, Out]) -> dict:
        row: dict = {"input": entry.input.model_dump(mode="json")}
        if entry.expected_output is not None:
            row["expected_output"] = entry.expected_output.model_dump(mode="json")
        if entry.metric is not None:
            row["metric"] = entry.metric.name
        return row

    @property
    def hash_dataset(self) -> str:
        """Stable 16-hex-char content hash over entries + name + version.

        For metric-free, fully-expected datasets the canonical row form
        is ``{"input": ..., "expected_output": ...}`` so pre-2-5 hashes
        (which used ``{"input": ..., "output": ...}``) are NOT preserved
        across the rename but are stable going forward.
        """
        payload = [self._row_payload(e) for e in self._entries]
        return hash_json(
            {"name": self.name, "version": self.version, "rows": payload}
        )

    def save(self, path: str | Path) -> None:
        """Write NDJSON: one entry object per line."""
        p = Path(path)
        with p.open("w", encoding="utf-8") as f:
            for e in self._entries:
                f.write(json.dumps(self._row_payload(e), sort_keys=True) + "\n")

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        in_cls: type[In],
        out_cls: type[Out],
        name: str = "",
        version: str = "",
        metric_registry: dict[str, Metric] | None = None,
    ) -> "Dataset[In, Out]":
        p = Path(path)
        entries: list[Entry[In, Out]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                inp = in_cls.model_validate(obj["input"])
                exp: Out | None = None
                if "expected_output" in obj:
                    exp = out_cls.model_validate(obj["expected_output"])
                metric: Metric | None = None
                if "metric" in obj and metric_registry is not None:
                    metric = metric_registry[obj["metric"]]
                entries.append(
                    Entry(input=inp, expected_output=exp, metric=metric)
                )
        return cls(entries, name=name, version=version)
