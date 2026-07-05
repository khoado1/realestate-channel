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

from scripts.store import pricing
from scripts.store.repository import get_repository

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

    repo = get_repository()
    call_id = repo.insert_call(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "provider": entry.get("provider"),
            "kind": entry.get("kind"),
            "operation": entry.get("operation"),
            "model": entry.get("model"),
            "method": entry.get("method"),
            "url": entry.get("url"),
            "request_json": jsonlib.dumps(request) if request is not None else None,
            "response_json": jsonlib.dumps(response) if response is not None else None,
            "http_status": entry.get("http_status"),
            "status": status,
            "error": entry.get("error"),
            "latency_ms": entry.get("latency_ms"),
            "input_units": cost["input_units"],
            "output_units": cost["output_units"],
            "unit_kind": cost["unit_kind"],
            "cost_usd": cost["cost_usd"],
            "cost_estimated": 1 if cost["estimated"] else 0,
        }
    )

    out_path = entry.get("out_path")
    if out_path and Path(out_path).exists():
        p = Path(out_path)
        mime = {".mp3": "audio/mpeg", ".mp4": "video/mp4"}.get(p.suffix, "application/octet-stream")
        kind = {".mp3": "audio", ".mp4": "video"}.get(p.suffix, "file")
        repo.insert_artifact(
            {
                "call_id": call_id, "direction": "out", "kind": kind,
                "path": str(p), "bytes": p.stat().st_size, "sha256": _sha256(p), "mime": mime,
            }
        )

    return call_id


def replay(call_id: int, execute: bool = False) -> dict:
    """Reconstruct a stored call. With execute=True, re-issue it (auth from env)."""
    row = get_repository().get_call(call_id)
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
