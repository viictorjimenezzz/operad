"""NDJSON job store — one `.jsonl` file per labeling job.

Rows have the shape produced by
`operad.train.callbacks.HumanFeedbackCallback`; Studio lets a human
fill in ``rating`` (1-5) and ``rationale`` (free text) per row.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class JobRow:
    id: str
    index: int
    run_id: str
    agent_path: str
    input: Any
    expected: Any
    predicted: Any
    rating: int | None
    rationale: str | None
    written_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "agent_path": self.agent_path,
            "input": self.input,
            "expected": self.expected,
            "predicted": self.predicted,
            "rating": self.rating,
            "rationale": self.rationale,
            "written_at": self.written_at,
        }


@dataclass
class JobSummary:
    name: str
    path: Path
    total_rows: int
    rated_rows: int

    @property
    def unrated(self) -> int:
        return max(0, self.total_rows - self.rated_rows)


def list_jobs(data_dir: Path) -> list[JobSummary]:
    """Return one `JobSummary` per `.jsonl` file in ``data_dir`` (newest first)."""
    if not data_dir.exists():
        return []
    items: list[JobSummary] = []
    for path in sorted(data_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        rows = read_rows(path)
        rated = sum(1 for r in rows if isinstance(r.rating, (int, float)))
        items.append(
            JobSummary(
                name=path.stem, path=path, total_rows=len(rows), rated_rows=rated
            )
        )
    return items


def read_rows(path: Path) -> list[JobRow]:
    if not path.exists():
        return []
    rows: list[JobRow] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        rating = data.get("rating")
        rating_int = int(rating) if isinstance(rating, (int, float)) else None
        rows.append(
            JobRow(
                id=str(data.get("id", "")),
                index=i,
                run_id=str(data.get("run_id", "")),
                agent_path=str(data.get("agent_path", "")),
                input=data.get("input"),
                expected=data.get("expected"),
                predicted=data.get("predicted"),
                rating=rating_int,
                rationale=data.get("rationale"),
                written_at=str(data.get("written_at", "")),
            )
        )
    return rows


def save_rating(
    path: Path,
    *,
    row_id: str,
    rating: int | None,
    rationale: str | None,
) -> bool:
    """Update one row's rating + rationale; atomic via temp-file swap."""
    rows = read_rows(path)
    updated = False
    for row in rows:
        if row.id == row_id:
            row.rating = rating
            row.rationale = rationale
            updated = True
            break
    if not updated:
        return False

    fd, tmp = tempfile.mkstemp(
        prefix=path.stem + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return True


__all__ = ["JobRow", "JobSummary", "list_jobs", "read_rows", "save_rating"]
