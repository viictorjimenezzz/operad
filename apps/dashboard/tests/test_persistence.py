from __future__ import annotations

import sqlite3
from collections import deque
from pathlib import Path

from operad_dashboard.persistence import SQLiteRunArchive
from operad_dashboard.runs import RunInfo


def _run_info(
    *,
    run_id: str,
    started_at: float,
    algorithm_path: str = "operad.algorithms.EvoGradient",
    synthetic: bool = False,
) -> RunInfo:
    info = RunInfo(
        run_id=run_id,
        started_at=started_at,
        last_event_at=started_at + 1.0,
        state="ended",
        algorithm_path=algorithm_path,
        events=deque(maxlen=1000),
        synthetic=synthetic,
    )
    info.events.append(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": algorithm_path,
            "kind": "algo_start",
            "payload": {},
            "started_at": started_at,
            "finished_at": None,
            "metadata": {},
        }
    )
    info.events.append(
        {
            "type": "algo_event",
            "run_id": run_id,
            "algorithm_path": algorithm_path,
            "kind": "algo_end",
            "payload": {"score": 0.9},
            "started_at": started_at + 1,
            "finished_at": started_at + 1,
            "metadata": {},
        }
    )
    info.event_counts = {"algo_start": 1, "algo_end": 1}
    return info


def test_upsert_snapshot_persists_summary_and_events(tmp_path: Path) -> None:
    store = SQLiteRunArchive(tmp_path)
    info = _run_info(run_id="r-1", started_at=100.0)
    info.notes_markdown = "hello"
    store.upsert_snapshot(info)

    restored = store.get_run("r-1")
    assert restored is not None
    assert restored["summary"]["run_id"] == "r-1"
    assert restored["summary"]["notes_markdown"] == "hello"
    assert len(restored["events"]) == 2


def test_set_notes_updates_existing_snapshot(tmp_path: Path) -> None:
    store = SQLiteRunArchive(tmp_path)
    info = _run_info(run_id="r-notes", started_at=100.0)
    store.upsert_snapshot(info)
    store.set_notes("r-notes", "**updated**")

    restored = store.get_run("r-notes")
    assert restored is not None
    assert restored["summary"]["notes_markdown"] == "**updated**"


def test_synthetic_run_skips_event_persistence(tmp_path: Path) -> None:
    store = SQLiteRunArchive(tmp_path)
    info = _run_info(run_id="r-synth", started_at=101.0, synthetic=True)
    store.upsert_snapshot(info)

    restored = store.get_run("r-synth")
    assert restored is not None
    assert restored["summary"]["synthetic"] is True
    assert restored["events"] == []


def test_migrations_apply_on_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _meta (
                migration TEXT PRIMARY KEY,
                applied_at REAL NOT NULL
            )
            """
        )

    store = SQLiteRunArchive(tmp_path)
    assert store.db_path == db_path
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "runs" in tables
        assert "events" in tables
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        assert "notes_markdown" in cols
        applied = {
            row[0]
            for row in conn.execute("SELECT migration FROM _meta").fetchall()
        }
        assert "0001_archive_schema.sql" in applied
        assert "0002_notes_markdown.sql" in applied
