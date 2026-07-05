"""Repository pattern for the call store — decouples callers from SQLite.

``scripts.store.calls`` owns the business logic (redaction, cost estimation,
auth re-injection for replay); this module owns persistence. A future backend
(e.g. Postgres, per docs/platform-architecture.md) implements ``CallRepository``
and drops in here via ``get_repository()`` — no changes needed in calls.py or
report.py, which only ever see plain dicts, never a ``sqlite3.Row`` or a
SQL statement.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from scripts.store import db


class CallRepository(ABC):
    """Persistence for recorded provider calls and their artifacts."""

    @abstractmethod
    def insert_call(self, row: dict) -> int:
        """Insert one call row (column name -> value). Returns the new call id."""

    @abstractmethod
    def insert_artifact(self, row: dict) -> None:
        """Insert one artifact row (column name -> value)."""

    @abstractmethod
    def get_call(self, call_id: int) -> dict | None:
        """Return the call row for ``call_id``, or ``None`` if it doesn't exist."""

    @abstractmethod
    def list_calls(self, limit: int) -> list[dict]:
        """Return the most recent ``limit`` call rows, newest first."""


class SQLiteCallRepository(CallRepository):
    def __init__(self, db_path: Path):
        self._conn = db.connect(db_path)

    def insert_call(self, row: dict) -> int:
        cur = self._conn.execute(
            """INSERT INTO calls (ts, provider, kind, operation, model, method, url,
                 request_json, response_json, http_status, status, error, latency_ms,
                 input_units, output_units, unit_kind, cost_usd, cost_estimated)
               VALUES (:ts, :provider, :kind, :operation, :model, :method, :url,
                 :request_json, :response_json, :http_status, :status, :error, :latency_ms,
                 :input_units, :output_units, :unit_kind, :cost_usd, :cost_estimated)""",
            row,
        )
        self._conn.commit()
        return cur.lastrowid

    def insert_artifact(self, row: dict) -> None:
        self._conn.execute(
            """INSERT INTO artifacts (call_id, direction, kind, path, bytes, sha256, mime)
               VALUES (:call_id, :direction, :kind, :path, :bytes, :sha256, :mime)""",
            row,
        )
        self._conn.commit()

    def get_call(self, call_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return dict(row) if row is not None else None

    def list_calls(self, limit: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT id, ts, provider, operation, status, input_units, output_units,
                 unit_kind, cost_usd, cost_estimated, latency_ms FROM calls
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


_repo: CallRepository | None = None


def get_repository() -> CallRepository:
    """Return the process-wide call repository singleton."""
    global _repo
    if _repo is None:
        from scripts.runtime import RuntimeConfig

        data_dir = Path(RuntimeConfig(paths=["DATA_DIR"]).DATA_DIR)
        _repo = SQLiteCallRepository(data_dir / "calls.db")
    return _repo
