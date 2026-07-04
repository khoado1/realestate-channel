"""SQLite schema + connection for the call store.

The schema is generic across providers: one row per API call plus optional
artifact rows for large streamed inputs/outputs kept on the filesystem.
"""

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    provider      TEXT,
    kind          TEXT,
    operation     TEXT,
    model         TEXT,
    method        TEXT,
    url           TEXT,
    request_json  TEXT,   -- redacted request body/params (enough to replay)
    response_json TEXT,   -- parsed JSON response (NULL for streamed/binary)
    http_status   INTEGER,
    status        TEXT,   -- 'ok' | 'error'
    error         TEXT,
    latency_ms    INTEGER,
    input_units   INTEGER,
    output_units  INTEGER,
    unit_kind     TEXT,   -- 'tokens' | 'chars' | NULL
    cost_usd      REAL,   -- NULL when unknown
    cost_estimated INTEGER -- 1 = estimated (from rate table), 0 = provider-billed
);

CREATE TABLE IF NOT EXISTS artifacts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id   INTEGER,
    direction TEXT,   -- 'in' | 'out'
    kind      TEXT,   -- 'audio' | 'video' | 'file'
    path      TEXT,
    bytes     INTEGER,
    sha256    TEXT,
    mime      TEXT,
    FOREIGN KEY (call_id) REFERENCES calls(id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the call-store database at db_path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn
