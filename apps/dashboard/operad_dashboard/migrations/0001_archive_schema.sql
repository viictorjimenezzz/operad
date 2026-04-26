CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    algorithm_path TEXT,
    state TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    parent_run_id TEXT,
    synthetic INTEGER NOT NULL DEFAULT 0,
    mermaid_text TEXT,
    summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts REAL NOT NULL,
    envelope_json TEXT NOT NULL,
    PRIMARY KEY (run_id, seq),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_algorithm_path ON runs(algorithm_path);
CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events(run_id, ts);
