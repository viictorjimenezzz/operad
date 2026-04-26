"""SQLite-backed archive store for completed dashboard runs."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .runs import RunInfo


_DB_FILENAME = "dashboard.sqlite"
_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class SQLiteRunArchive:
    """Small stdlib-sqlite mirror of terminal run snapshots."""

    def __init__(self, data_dir: Path | str) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / _DB_FILENAME
        self._apply_migrations()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def upsert_snapshot(self, info: RunInfo) -> None:
        summary = info.summary()
        summary_json = _canonical_json(summary)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    algorithm_path,
                    state,
                    started_at,
                    ended_at,
                    parent_run_id,
                    synthetic,
                    mermaid_text,
                    summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    algorithm_path=excluded.algorithm_path,
                    state=excluded.state,
                    started_at=excluded.started_at,
                    ended_at=excluded.ended_at,
                    parent_run_id=excluded.parent_run_id,
                    synthetic=excluded.synthetic,
                    mermaid_text=excluded.mermaid_text,
                    summary_json=excluded.summary_json
                """,
                (
                    info.run_id,
                    info.algorithm_path,
                    info.state,
                    info.started_at,
                    info.last_event_at,
                    info.parent_run_id,
                    1 if info.synthetic else 0,
                    info.mermaid,
                    summary_json,
                ),
            )

            conn.execute("DELETE FROM events WHERE run_id = ?", (info.run_id,))
            if not info.synthetic:
                for seq, envelope in enumerate(info.events):
                    conn.execute(
                        """
                        INSERT INTO events (run_id, seq, ts, envelope_json)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            info.run_id,
                            seq,
                            _envelope_timestamp(envelope, fallback=info.last_event_at),
                            _canonical_json(envelope),
                        ),
                    )

    def list_runs(
        self,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        algorithm: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        algo_pattern = None if algorithm is None else f"%.{algorithm}"
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT summary_json
                FROM runs
                WHERE (? IS NULL OR started_at >= ?)
                  AND (? IS NULL OR started_at <= ?)
                  AND (
                      ? IS NULL
                      OR algorithm_path = ?
                      OR algorithm_path LIKE ?
                  )
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (
                    from_ts,
                    from_ts,
                    to_ts,
                    to_ts,
                    algorithm,
                    algorithm,
                    algo_pattern,
                    safe_limit,
                ),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            event_rows = conn.execute(
                """
                SELECT envelope_json
                FROM events
                WHERE run_id = ?
                ORDER BY seq ASC
                """,
                (run_id,),
            ).fetchall()
        return {
            "summary": json.loads(row[0]),
            "events": [json.loads(ev[0]) for ev in event_rows],
        }

    def get_mermaid(self, run_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mermaid_text FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        value = row[0]
        return value if isinstance(value, str) and value else None

    def delete_run(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    def iter_export_records(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            run_rows = conn.execute(
                "SELECT run_id, summary_json FROM runs ORDER BY started_at DESC"
            ).fetchall()
            out: list[dict[str, Any]] = []
            for run_id, summary_json in run_rows:
                event_rows = conn.execute(
                    """
                    SELECT envelope_json
                    FROM events
                    WHERE run_id = ?
                    ORDER BY seq ASC
                    """,
                    (run_id,),
                ).fetchall()
                out.append(
                    {
                        "summary": json.loads(summary_json),
                        "events": [json.loads(ev[0]) for ev in event_rows],
                    }
                )
        return out

    def _apply_migrations(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _meta (
                    migration TEXT PRIMARY KEY,
                    applied_at REAL NOT NULL
                )
                """
            )
            applied = {
                row[0]
                for row in conn.execute("SELECT migration FROM _meta").fetchall()
            }
            for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                if path.name in applied:
                    continue
                sql = path.read_text(encoding="utf-8")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO _meta (migration, applied_at) VALUES (?, ?)",
                    (path.name, time.time()),
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _envelope_timestamp(envelope: dict[str, Any], *, fallback: float) -> float:
    started = envelope.get("started_at")
    if isinstance(started, (int, float)):
        return float(started)
    finished = envelope.get("finished_at")
    if isinstance(finished, (int, float)):
        return float(finished)
    return fallback


__all__ = ["SQLiteRunArchive"]
