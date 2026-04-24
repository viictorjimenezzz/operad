"""NDJSON job store — `list_jobs`, `read_rows`, `save_rating`."""

from __future__ import annotations

import json
from pathlib import Path

from operad_studio.jobs import list_jobs, read_rows, save_rating


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _row(id_: str, rating: int | None = None) -> dict:
    return {
        "id": id_,
        "run_id": "r1",
        "agent_path": "Talker",
        "input": {"text": f"x{id_}"},
        "expected": None,
        "predicted": {"text": f"y{id_}"},
        "rating": rating,
        "rationale": None,
        "written_at": "2026-04-24T00:00:00+00:00",
    }


def test_list_jobs_empty_dir(tmp_path: Path) -> None:
    assert list_jobs(tmp_path) == []


def test_list_jobs_reports_unrated_count(tmp_path: Path) -> None:
    _write_rows(
        tmp_path / "a.jsonl",
        [_row("a1", rating=5), _row("a2"), _row("a3")],
    )
    _write_rows(tmp_path / "b.jsonl", [_row("b1", rating=3)])
    jobs = {j.name: j for j in list_jobs(tmp_path)}
    assert jobs["a"].total_rows == 3
    assert jobs["a"].rated_rows == 1
    assert jobs["a"].unrated == 2
    assert jobs["b"].unrated == 0


def test_read_rows_skips_blank_and_broken_lines(tmp_path: Path) -> None:
    p = tmp_path / "j.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(_row("x1")),
                "",
                "not json",
                json.dumps(_row("x2", rating=4)),
            ]
        ),
        encoding="utf-8",
    )
    rows = read_rows(p)
    assert [r.id for r in rows] == ["x1", "x2"]
    assert rows[1].rating == 4


def test_save_rating_atomic_update(tmp_path: Path) -> None:
    p = tmp_path / "j.jsonl"
    _write_rows(p, [_row("a"), _row("b"), _row("c")])
    assert save_rating(p, row_id="b", rating=5, rationale="great") is True
    rows = read_rows(p)
    b = next(r for r in rows if r.id == "b")
    assert b.rating == 5
    assert b.rationale == "great"
    # Others untouched.
    assert read_rows(p)[0].id == "a"
    assert len(read_rows(p)) == 3


def test_save_rating_missing_row_returns_false(tmp_path: Path) -> None:
    p = tmp_path / "j.jsonl"
    _write_rows(p, [_row("a")])
    assert save_rating(p, row_id="nope", rating=5, rationale="") is False
