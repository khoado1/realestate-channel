"""Record and replay provider API calls.

``record`` is installed as the HTTP recorder; it persists one row per call
(with cost/usage) plus artifact rows for streamed audio/video. ``replay``
reconstructs a stored request and can re-issue it (auth re-injected from env).
"""

import hashlib
import json as jsonlib
import os
from datetime import datetime
from pathlib import Path

from scripts.store import db, pricing

_conn = None
_db_path: Path | None = None
_artifacts_dir: Path | None = None

# Redact any request field whose key hints at a secret (auth normally lives in
# headers, which are never recorded — this is defense in depth).
_SECRET_HINTS = ("key", "token", "authorization", "secret", "password")

# Auth header re-injection for replay, per provider.
_AUTH = {
    "claude": lambda: {
        "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
    "elevenlabs": lambda: {"xi-api-key": os.getenv("ELEVENLABS_API_KEY", "")},
    "heygen": lambda: {"X-Api-Key": os.getenv("HEYGEN_API_KEY", ""), "Content-Type": "application/json"},
    "hyperframes": lambda: {
        "Authorization": f"Bearer {os.getenv('HYPERFRAMES_API_KEY', '') or os.getenv('ELEVENLABS_API_KEY', '')}",
        "Content-Type": "application/json",
    },
}


def _resolve_paths() -> tuple[Path, Path]:
    global _db_path, _artifacts_dir
    if _db_path is None:
        from scripts.runtime import RuntimeConfig

        data_dir = Path(RuntimeConfig(paths=["DATA_DIR"]).DATA_DIR)
        _db_path = data_dir / "calls.db"
        _artifacts_dir = data_dir / "artifacts"
    return _db_path, _artifacts_dir


def _conn_get():
    global _conn
    if _conn is None:
        db_path, _ = _resolve_paths()
        _conn = db.connect(db_path)
    return _conn


def _redact(obj):
    if isinstance(obj, dict):
        return {
            k: ("***" if any(h in k.lower() for h in _SECRET_HINTS) else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def record(entry: dict) -> int:
    """Persist one call. Installed as the HTTP recorder; never raises."""
    cost = pricing.estimate(entry)
    request = _redact(entry.get("request"))
    response = entry.get("response")
    status = "error" if entry.get("error") else "ok"

    conn = _conn_get()
    cur = conn.execute(
        """INSERT INTO calls (ts, provider, kind, operation, model, method, url,
             request_json, response_json, http_status, status, error, latency_ms,
             input_units, output_units, unit_kind, cost_usd, cost_estimated)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            entry.get("provider"), entry.get("kind"), entry.get("operation"), entry.get("model"),
            entry.get("method"), entry.get("url"),
            jsonlib.dumps(request) if request is not None else None,
            jsonlib.dumps(response) if response is not None else None,
            entry.get("http_status"), status, entry.get("error"), entry.get("latency_ms"),
            cost["input_units"], cost["output_units"], cost["unit_kind"],
            cost["cost_usd"], 1 if cost["estimated"] else 0,
        ),
    )
    call_id = cur.lastrowid

    out_path = entry.get("out_path")
    if out_path and Path(out_path).exists():
        p = Path(out_path)
        mime = {".mp3": "audio/mpeg", ".mp4": "video/mp4"}.get(p.suffix, "application/octet-stream")
        kind = {".mp3": "audio", ".mp4": "video"}.get(p.suffix, "file")
        conn.execute(
            "INSERT INTO artifacts (call_id, direction, kind, path, bytes, sha256, mime) VALUES (?,?,?,?,?,?,?)",
            (call_id, "out", kind, str(p), p.stat().st_size, _sha256(p), mime),
        )

    conn.commit()
    return call_id


def replay(call_id: int, execute: bool = False) -> dict:
    """Reconstruct a stored call. With execute=True, re-issue it (auth from env)."""
    conn = _conn_get()
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    if row is None:
        raise KeyError(f"No call with id {call_id}")

    body = jsonlib.loads(row["request_json"]) if row["request_json"] else None
    plan = {"method": row["method"], "url": row["url"], "provider": row["provider"], "body": body}
    if not execute:
        return plan

    from scripts.providers import http  # lazy: avoids a store<->providers import cycle

    headers = _AUTH.get(row["provider"], lambda: {})()
    plan["response"] = http.request_json(row["method"], row["url"], headers=headers, json=body)
    return plan
